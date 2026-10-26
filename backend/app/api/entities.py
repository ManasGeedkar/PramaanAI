from typing import Optional, List, Dict, Any, Set
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import Application, Entity, EntityOccurrence, Document, Finding

router = APIRouter(prefix="/api/entities", tags=["entities"])

def format_inst_label(inst_id: str, full_name: str) -> str:
    """Returns human readable institution short name + ID, e.g. 'Rajkot Kalan CoE · INST07'."""
    short = full_name or ""
    short = short.replace("College of Engineering", "CoE")
    short = short.replace("Institute of Information Technology", "IIT")
    short = short.replace("Institute of Engineering & Management", "IEM")
    short = short.replace("Institute of Engineering and Management", "IEM")
    short = short.replace("Institute of Technology", "IT")
    short = short.replace("Engineering College", "Engg College")
    short = short.replace("Polytechnic & Engineering College", "PEC")
    short = short.replace("Polytechnic and Engineering College", "PEC")
    short = short.replace("School of Engineering", "SoE")
    short = short.strip()
    return f"{short} · {inst_id}"

def format_entity_label(entity: Entity) -> str:
    """Returns human-readable label for entity node."""
    if entity.entity_type == "faculty":
        return entity.display
    elif entity.entity_type == "fire_noc_no":
        val = entity.key
        return f"Fire NOC: {val}"
    elif entity.entity_type == "deed_no":
        val = entity.key
        return f"Sale Deed: {val}"
    elif entity.entity_type == "survey_no":
        val = entity.key
        return f"Survey: {val}"
    elif entity.entity_type in ("photo", "photo_hash"):
        if "lab" in entity.display.lower() or "lab" in entity.key.lower():
            return "Lab Photo"
        clean = entity.display.replace("Photo ", "")
        return clean
    return entity.display

@router.get("/graph")
def get_entity_graph(
    application_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_session)
):
    """
    Returns nodes and edges formatted for React Flow (@xyflow/react).
    If application_id is provided, returns the entity graph connected to that application:
      Left: Current application
      Middle: Entities (shared by other apps, or all)
      Right: Related applications
      Edges flow strictly left-to-right without line crossings.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    target_app_ids: Set[int] = set()
    target_entity_ids: Set[int] = set()

    if application_id is not None:
        target_app_ids.add(application_id)
        # Find all entities for this application
        occs = session.exec(
            select(EntityOccurrence).where(EntityOccurrence.application_id == application_id)
        ).all()
        for occ in occs:
            target_entity_ids.add(occ.entity_id)

        # Also find other applications that share these entities
        if target_entity_ids:
            connected_occs = session.exec(
                select(EntityOccurrence).where(EntityOccurrence.entity_id.in_(target_entity_ids))
            ).all()
            for co in connected_occs:
                target_app_ids.add(co.application_id)
    else:
        # Global graph: find entities that appear in 2 or more applications
        all_occs = session.exec(select(EntityOccurrence)).all()
        entity_app_map: Dict[int, Set[int]] = {}
        for occ in all_occs:
            if occ.entity_id not in entity_app_map:
                entity_app_map[occ.entity_id] = set()
            entity_app_map[occ.entity_id].add(occ.application_id)

        for ent_id, app_ids in entity_app_map.items():
            if len(app_ids) >= 2:
                target_entity_ids.add(ent_id)
                target_app_ids.update(app_ids)

    # Fetch applications
    apps = session.exec(
        select(Application).where(Application.id.in_(target_app_ids))
    ).all() if target_app_ids else []
    app_map = {a.id: a for a in apps}

    # Fetch entities
    entities = session.exec(
        select(Entity).where(Entity.id.in_(target_entity_ids))
    ).all() if target_entity_ids else []
    entity_map = {e.id: e for e in entities}

    # Fetch all occurrences for target entities to build full occurrence details
    all_target_occs = session.exec(
        select(EntityOccurrence).where(EntityOccurrence.entity_id.in_(target_entity_ids))
    ).all() if target_entity_ids else []

    # Preload documents
    doc_ids = {o.document_id for o in all_target_occs if o.document_id}
    docs = session.exec(select(Document).where(Document.id.in_(doc_ids))).all() if doc_ids else []
    doc_map = {d.id: d for d in docs}

    # Preload all applications that may be referenced in occurrences
    occ_app_ids = {o.application_id for o in all_target_occs}
    all_occ_apps = session.exec(select(Application).where(Application.id.in_(occ_app_ids))).all() if occ_app_ids else []
    all_app_map = {a.id: a for a in all_occ_apps}

    # Group occurrences by entity_id
    entity_occurrences_map: Dict[int, List[Dict[str, Any]]] = {}
    for occ in all_target_occs:
        app_obj = all_app_map.get(occ.application_id)
        doc_obj = doc_map.get(occ.document_id)
        
        is_photo = False
        thumb_url = None
        if doc_obj:
            is_photo = "photo" in doc_obj.doc_type or doc_obj.file_path.lower().endswith(('.jpg', '.jpeg', '.png'))
            if is_photo:
                thumb_url = f"/api/documents/{doc_obj.id}/file"

        occ_info = {
            "application_id": occ.application_id,
            "institution_id": app_obj.institution_id if app_obj else f"APP#{occ.application_id}",
            "institution_name": app_obj.institution_name if app_obj else "Institution",
            "risk_band": app_obj.risk_band if app_obj else "Low",
            "document_id": occ.document_id,
            "doc_type": doc_obj.doc_type if doc_obj else "document",
            "academic_year": occ.academic_year,
            "thumbnail_url": thumb_url
        }
        if occ.entity_id not in entity_occurrences_map:
            entity_occurrences_map[occ.entity_id] = []
        entity_occurrences_map[occ.entity_id].append(occ_info)

    # Layout nodes:
    # If application_id is provided: focus app on left, entities in center, other apps on right
    if application_id is not None:
        focus_app = app_map.get(application_id)
        other_apps = [a for a in apps if a.id != application_id]

        # Group entities: shared entities grouped by the related application they connect to,
        # then unshared entities
        shared_by_app: Dict[int, List[Entity]] = {a.id: [] for a in other_apps}
        unshared_entities: List[Entity] = []

        for e in entities:
            occs = entity_occurrences_map.get(e.id, [])
            other_insts = [o["application_id"] for o in occs if o["application_id"] != application_id]
            if other_insts:
                dest_app_id = other_insts[0]
                if dest_app_id in shared_by_app:
                    shared_by_app[dest_app_id].append(e)
                else:
                    shared_by_app.setdefault(dest_app_id, []).append(e)
            else:
                unshared_entities.append(e)

        # Calculate coordinates for clean non-crossing layout
        entity_positions: Dict[int, Dict[str, int]] = {}
        app_positions: Dict[int, Dict[str, int]] = {}
        
        curr_y = 50
        y_step = 85

        # Position shared entities grouped by related app
        for other_app in other_apps:
            grp_ents = shared_by_app.get(other_app.id, [])
            if not grp_ents:
                continue
            start_y = curr_y
            for e in grp_ents:
                entity_positions[e.id] = {"x": 420, "y": curr_y}
                curr_y += y_step
            end_y = curr_y - y_step
            # Place related app on right, vertically centered with its entities
            app_positions[other_app.id] = {"x": 840, "y": (start_y + end_y) // 2}
            curr_y += 35  # vertical spacing between related application blocks

        shared_end_y = curr_y

        # Position unshared entities
        for e in unshared_entities:
            entity_positions[e.id] = {"x": 420, "y": curr_y}
            curr_y += y_step

        # Place focus app on left, vertically centered relative to shared entities
        total_shared = sum(len(shared_by_app.get(a.id, [])) for a in other_apps)
        mid_y = (50 + shared_end_y - 35) // 2 if total_shared > 0 else (curr_y // 2)
        if focus_app:
            app_positions[focus_app.id] = {"x": 60, "y": max(60, mid_y)}

            nodes.append({
                "id": f"app-{focus_app.id}",
                "type": "application",
                "data": {
                    "label": format_inst_label(focus_app.institution_id, focus_app.institution_name),
                    "institution_id": focus_app.institution_id,
                    "institution_name": focus_app.institution_name,
                    "short_name": format_inst_label(focus_app.institution_id, focus_app.institution_name),
                    "application_id": focus_app.id,
                    "category": focus_app.category,
                    "risk_band": focus_app.risk_band or "Low",
                    "risk_score": focus_app.risk_score,
                    "is_focus": True
                },
                "position": app_positions[focus_app.id]
            })

        for a in other_apps:
            pos = app_positions.get(a.id, {"x": 840, "y": 100})
            nodes.append({
                "id": f"app-{a.id}",
                "type": "application",
                "data": {
                    "label": format_inst_label(a.institution_id, a.institution_name),
                    "institution_id": a.institution_id,
                    "institution_name": a.institution_name,
                    "short_name": format_inst_label(a.institution_id, a.institution_name),
                    "application_id": a.id,
                    "category": a.category,
                    "risk_band": a.risk_band or "Low",
                    "risk_score": a.risk_score,
                    "is_focus": False
                },
                "position": pos
            })

        for e in entities:
            occs_list = entity_occurrences_map.get(e.id, [])
            pos = entity_positions.get(e.id, {"x": 420, "y": 100})
            thumb_url = None
            if e.entity_type in ("photo", "photo_hash"):
                for occ_item in occs_list:
                    if occ_item.get("thumbnail_url"):
                        thumb_url = occ_item["thumbnail_url"]
                        break

            nodes.append({
                "id": f"ent-{e.id}",
                "type": "entity",
                "data": {
                    "label": format_entity_label(e),
                    "entity_type": e.entity_type,
                    "key": e.key,
                    "entity_id": e.id,
                    "occurrences": occs_list,
                    "is_shared": len(occs_list) > 1,
                    "thumbnail_url": thumb_url
                },
                "position": pos
            })

        # Edges formatted strictly Left-to-Right
        added_edges = set()
        for occ in all_target_occs:
            if occ.application_id not in target_app_ids or occ.entity_id not in target_entity_ids:
                continue
            edge_key = (occ.application_id, occ.entity_id)
            if edge_key in added_edges:
                continue
            added_edges.add(edge_key)

            ent = entity_map.get(occ.entity_id)
            if not ent:
                continue

            ent_type = ent.entity_type
            if ent_type == "photo":
                edge_label = "photo"
            elif ent_type == "faculty":
                edge_label = "faculty"
            elif ent_type == "fire_noc_no":
                edge_label = "fire_noc_no"
            elif ent_type == "deed_no":
                edge_label = "deed_no"
            elif ent_type == "survey_no":
                edge_label = "survey_no"
            else:
                edge_label = ent_type

            is_shared = len(entity_occurrences_map.get(occ.entity_id, [])) > 1

            if occ.application_id == application_id:
                # Left -> Middle (Focus App to Entity)
                edges.append({
                    "id": f"edge-focus-app{occ.application_id}-ent{occ.entity_id}",
                    "source": f"app-{occ.application_id}",
                    "sourceHandle": "right",
                    "target": f"ent-{occ.entity_id}",
                    "targetHandle": "left",
                    "label": edge_label,
                    "is_shared": is_shared,
                    "animated": is_shared
                })
            else:
                # Middle -> Right (Entity to Related App)
                edges.append({
                    "id": f"edge-ent{occ.entity_id}-app{occ.application_id}",
                    "source": f"ent-{occ.entity_id}",
                    "sourceHandle": "right",
                    "target": f"app-{occ.application_id}",
                    "targetHandle": "left",
                    "label": edge_label,
                    "is_shared": is_shared,
                    "animated": is_shared
                })

    else:
        # Global view layout
        for idx, a in enumerate(apps):
            nodes.append({
                "id": f"app-{a.id}",
                "type": "application",
                "data": {
                    "label": format_inst_label(a.institution_id, a.institution_name),
                    "institution_id": a.institution_id,
                    "institution_name": a.institution_name,
                    "short_name": format_inst_label(a.institution_id, a.institution_name),
                    "application_id": a.id,
                    "category": a.category,
                    "risk_band": a.risk_band or "Low",
                    "risk_score": a.risk_score,
                    "is_focus": False
                },
                "position": {"x": 80, "y": (idx * 130) + 50}
            })

        for idx, e in enumerate(entities):
            occs_list = entity_occurrences_map.get(e.id, [])
            thumb_url = None
            if e.entity_type in ("photo", "photo_hash"):
                for occ_item in occs_list:
                    if occ_item.get("thumbnail_url"):
                        thumb_url = occ_item["thumbnail_url"]
                        break

            nodes.append({
                "id": f"ent-{e.id}",
                "type": "entity",
                "data": {
                    "label": format_entity_label(e),
                    "entity_type": e.entity_type,
                    "key": e.key,
                    "entity_id": e.id,
                    "occurrences": occs_list,
                    "is_shared": len(occs_list) > 1,
                    "thumbnail_url": thumb_url
                },
                "position": {"x": 520, "y": (idx * 90) + 40}
            })

        if target_app_ids and target_entity_ids:
            relevant_occs = [o for o in all_target_occs if o.application_id in target_app_ids]
            added_edges = set()
            for occ in relevant_occs:
                edge_key = (occ.application_id, occ.entity_id)
                if edge_key in added_edges:
                    continue
                added_edges.add(edge_key)

                ent = entity_map.get(occ.entity_id)
                label = ent.entity_type if ent else "connected"
                is_shared = len(entity_occurrences_map.get(occ.entity_id, [])) > 1

                edges.append({
                    "id": f"edge-app{occ.application_id}-ent{occ.entity_id}",
                    "source": f"app-{occ.application_id}",
                    "sourceHandle": "right",
                    "target": f"ent-{occ.entity_id}",
                    "targetHandle": "left",
                    "label": label,
                    "is_shared": is_shared,
                    "animated": is_shared
                })

    return {
        "nodes": nodes,
        "edges": edges
    }
