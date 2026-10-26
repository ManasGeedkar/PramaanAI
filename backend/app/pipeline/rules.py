import math
import re
import json
from typing import Dict, Any, List, Optional, Tuple
import yaml
from sqlmodel import Session, select

from app.models import Application, Document, ExtractedField, Finding, RuleSet
from app.config import settings

def get_var(data: Any, path: str, default: Any = None) -> Any:
    if not path:
        return data
    parts = str(path).split(".")
    curr = data
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            return default
    return curr

def evaluate_json_logic(logic: Any, data: Dict[str, Any]) -> Any:
    """Lightweight evaluator for json-logic rules in rules.yaml."""
    if not isinstance(logic, dict):
        return logic

    op = list(logic.keys())[0]
    args = logic[op]
    if not isinstance(args, list):
        args = [args]

    if op == "var":
        var_path = args[0] if args else ""
        def_val = args[1] if len(args) > 1 else None
        return get_var(data, var_path, def_val)

    elif op == "and":
        return all(bool(evaluate_json_logic(a, data)) for a in args)

    elif op == "or":
        return any(bool(evaluate_json_logic(a, data)) for a in args)

    elif op == "!":
        return not bool(evaluate_json_logic(args[0], data))

    elif op == "!!":
        val = evaluate_json_logic(args[0], data)
        return bool(val and val not in ("null", "None", ""))

    elif op in (">=", ">", "<=", "<", "==", "!="):
        v1 = evaluate_json_logic(args[0], data)
        v2 = evaluate_json_logic(args[1], data)
        if v1 is None or v2 is None or v1 in ("null", "None") or v2 in ("null", "None"):
            return False

        # Try converting to float for numeric comparison
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            n1, n2 = float(v1), float(v2)
        else:
            try:
                n1, n2 = float(v1), float(v2)
            except (ValueError, TypeError):
                n1, n2 = str(v1), str(v2)

        if op == ">=": return n1 >= n2
        elif op == ">": return n1 > n2
        elif op == "<=": return n1 <= n2
        elif op == "<": return n1 < n2
        elif op == "==": return n1 == n2
        elif op == "!=": return n1 != n2

    elif op == "*":
        vals = [evaluate_json_logic(a, data) for a in args]
        res = 1.0
        for v in vals:
            try:
                res *= float(v)
            except (ValueError, TypeError):
                res *= 0.0
        return res

    elif op == "+":
        vals = [evaluate_json_logic(a, data) for a in args]
        res = 0.0
        for v in vals:
            try:
                res += float(v)
            except (ValueError, TypeError):
                pass
        return res

    return False

def build_rule_context(
    app: Application,
    documents: List[Document],
    fields: List[ExtractedField],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Builds context described in rules.yaml:
      app.* -> application declared block + category
      docs.<doc_type>.<field> -> extracted values
      derived.required_faculty, derived.total_proposed_intake
      params.*
    """
    # Load application.json if available
    app_folder = settings.APPLICATIONS_DIR / app.folder
    app_json_path = app_folder / "application.json"
    declared = {}
    if app_json_path.exists():
        try:
            with open(app_json_path, "r", encoding="utf-8") as f:
                app_data = json.load(f)
                declared = app_data.get("declared", {})
        except Exception:
            declared = {}

    app_context = dict(declared)
    app_context["category"] = app.category

    # Map extracted values per doc_type
    doc_id_to_type = {d.id: d.doc_type for d in documents}
    docs_context: Dict[str, Dict[str, Any]] = {}

    for d in documents:
        docs_context.setdefault(d.doc_type, {})

    for f in fields:
        doc_type = doc_id_to_type.get(f.document_id)
        if doc_type and f.value not in (None, "null"):
            # Parse number if numeric
            val = f.value
            try:
                if "." in val:
                    val = float(val)
                else:
                    val = int(val)
            except (ValueError, TypeError):
                pass
            docs_context[doc_type][f.name] = val

    # Derived values
    total_proposed_intake = declared.get("total_proposed_intake", 0)
    ratio = params.get("faculty_student_ratio", 20)
    required_faculty = math.ceil(total_proposed_intake / ratio) if ratio else 0

    derived_context = {
        "total_proposed_intake": total_proposed_intake,
        "required_faculty": required_faculty
    }

    return {
        "app": app_context,
        "docs": docs_context,
        "derived": derived_context,
        "params": params
    }

def format_message(template: str, context: Dict[str, Any]) -> str:
    """Fills {placeholders} in rule message template."""
    def replacer(match):
        var_path = match.group(1).strip()
        val = get_var(context, var_path, "")
        return str(val) if val is not None else ""

    return re.sub(r"\{([^}]+)\}", replacer, template)

def evaluate_rules(
    app: Application,
    documents: List[Document],
    fields: List[ExtractedField],
    session: Session
) -> List[Finding]:
    """
    Evaluates rules from the active RuleSet (or settings.rules).
    Generates RULE_FAIL findings with rule_id and Section 4.3 evidence.
    """
    # Fetch active RuleSet from database if available
    active_ruleset = session.exec(
        select(RuleSet).where(RuleSet.active == True)
    ).first()

    if active_ruleset and active_ruleset.yaml_text:
        rules_cfg = yaml.safe_load(active_ruleset.yaml_text) or {}
    else:
        rules_cfg = settings.rules or {}

    params = rules_cfg.get("params", {})
    rules_list = rules_cfg.get("rules", [])

    context = build_rule_context(app, documents, fields, params)
    findings: List[Finding] = []

    doc_map = {d.doc_type: d for d in documents}
    field_map = {}
    for f in fields:
        doc = doc_map.get(d.doc_type) if (d := next((doc for doc in documents if doc.id == f.document_id), None)) else None
        if doc:
            field_map[(doc.doc_type, f.name)] = f

    for rule in rules_list:
        rule_id = rule.get("id")
        applies_to = rule.get("applies_to", [])
        if applies_to and app.category not in applies_to:
            continue

        logic = rule.get("logic", {})
        passed = evaluate_json_logic(logic, context)

        if not passed:
            severity = rule.get("severity", "critical")
            title = rule.get("title", f"Rule {rule_id} Failed")
            raw_msg = rule.get("message", "Compliance rule failed")
            formatted_msg = format_message(raw_msg, context)

            ev_cfg = rule.get("evidence", {})
            doc_type = ev_cfg.get("doc_type")
            field_name = ev_cfg.get("field")

            evidence_items = []
            doc_rec = doc_map.get(doc_type)
            ef = field_map.get((doc_type, field_name))

            if doc_rec:
                bbox = None
                if ef and ef.bbox_json:
                    try:
                        bbox = json.loads(ef.bbox_json)
                    except Exception:
                        bbox = None
                evidence_items.append({
                    "document_id": doc_rec.id,
                    "doc_type": doc_type,
                    "page": ef.page if ef else 1,
                    "bbox": bbox,
                    "field": field_name,
                    "value": str(ef.value) if (ef and ef.value is not None) else None
                })

            evidence = {
                "items": evidence_items,
                "expected": f"Rule {rule_id} pass",
                "method": "rules_engine",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": formatted_msg
            }

            f = Finding(
                application_id=app.id,
                document_id=doc_rec.id if doc_rec else None,
                code="RULE_FAIL",
                severity=severity,
                title=title,
                message=formatted_msg,
                rule_id=rule_id,
                evidence_json=json.dumps(evidence),
                confidence=1.0,
                status="open"
            )
            findings.append(f)

    return findings
