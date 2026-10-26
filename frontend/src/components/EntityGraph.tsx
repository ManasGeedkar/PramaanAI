import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Users,
  Flame,
  FileText,
  MapPin,
  Camera,
  ExternalLink,
  Info,
  X,
  AlertCircle,
  Building2,
  Filter,
} from 'lucide-react';
import { api } from '../api/client';

interface Occurrence {
  application_id: number;
  institution_id: string;
  institution_name?: string;
  risk_band?: string;
  document_id: number;
  doc_type: string;
  role?: string;
  academic_year?: string;
  thumbnail_url?: string;
}

interface SelectedEntity {
  id: string;
  label: string;
  entity_type: string;
  thumbnail_url?: string;
  occurrences: Occurrence[];
}

// Custom Node for Applications
const ApplicationNode = ({ data }: NodeProps) => {
  const nodeData = data as any;
  const isHigh = nodeData.risk_band === 'High';
  const isMedium = nodeData.risk_band === 'Medium';

  const borderClass = isHigh
    ? 'border-red-500 bg-red-50/95 text-red-950 ring-2 ring-red-200'
    : isMedium
    ? 'border-amber-500 bg-amber-50/95 text-amber-950 ring-2 ring-amber-200'
    : 'border-emerald-500 bg-emerald-50/95 text-emerald-950 ring-2 ring-emerald-200';

  const badgeClass = isHigh
    ? 'bg-red-600 text-white'
    : isMedium
    ? 'bg-amber-600 text-white'
    : 'bg-emerald-600 text-white';

  return (
    <div
      className={`px-3.5 py-2.5 rounded-lg border-2 shadow-sm min-w-[210px] max-w-[250px] text-left transition-all relative ${borderClass}`}
    >
      {/* Target handle on Left */}
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        className="!w-2.5 !h-2.5 !bg-slate-400 !border-white !border-2"
      />

      <div className="flex items-center justify-between gap-1.5 mb-1">
        <span className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-slate-700">
          <Building2 className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
          {nodeData.is_focus ? (
            <span className="text-primary-700 font-extrabold">Current Application</span>
          ) : (
            nodeData.institution_id || 'Application'
          )}
        </span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shadow-2xs ${badgeClass}`}>
          {nodeData.risk_band || 'Active'}
        </span>
      </div>

      <div className="text-xs font-bold leading-snug text-slate-900 break-words">
        {String(nodeData.label || `${nodeData.institution_id} - ${nodeData.institution_name}`)}
      </div>

      {nodeData.risk_score !== undefined && (
        <div className="mt-1 text-[10px] font-medium text-slate-500">
          Risk Score: <span className="font-semibold text-slate-700">{nodeData.risk_score}</span>
        </div>
      )}

      {/* Source handle on Right */}
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        className="!w-2.5 !h-2.5 !bg-slate-400 !border-white !border-2"
      />
    </div>
  );
};

// Custom Node for Entities
const EntityCustomNode = ({ data }: NodeProps) => {
  const nodeData = data as any;
  const occurrences = Array.isArray(nodeData.occurrences) ? nodeData.occurrences : [];
  const occurrenceCount = occurrences.length > 0 ? occurrences.length : 1;
  const isCrossApp = occurrenceCount > 1 || Boolean(nodeData.is_shared);
  const isPhoto = nodeData.entity_type === 'photo' || nodeData.entity_type === 'photo_hash';

  const getIcon = () => {
    switch (nodeData.entity_type) {
      case 'faculty':
        return <Users className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />;
      case 'fire_noc_no':
        return <Flame className="w-3.5 h-3.5 text-red-600 flex-shrink-0" />;
      case 'deed_no':
        return <FileText className="w-3.5 h-3.5 text-purple-600 flex-shrink-0" />;
      case 'survey_no':
        return <MapPin className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />;
      case 'photo':
      case 'photo_hash':
        return <Camera className="w-3.5 h-3.5 text-pink-600 flex-shrink-0" />;
      default:
        return <Info className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />;
    }
  };

  const thumbUrl = nodeData.thumbnail_url || (occurrences.find((o: Occurrence) => o.thumbnail_url)?.thumbnail_url);

  // Purple Multi-App Match highlight for shared entities
  const borderClass = isCrossApp
    ? 'border-purple-500 bg-purple-50/95 ring-2 ring-purple-300 shadow-md hover:border-purple-600'
    : 'border-slate-300 bg-white hover:border-slate-400 shadow-xs';

  return (
    <div
      className={`px-3 py-2 rounded-lg border text-left cursor-pointer transition-all min-w-[190px] max-w-[260px] relative ${borderClass}`}
    >
      {/* Target handle on Left */}
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        className={`!w-2.5 !h-2.5 !border-white !border-2 ${isCrossApp ? '!bg-purple-600' : '!bg-slate-400'}`}
      />

      {isPhoto ? (
        <div className="flex items-center gap-2.5">
          {thumbUrl ? (
            <img
              src={thumbUrl}
              alt="Thumbnail"
              className="w-10 h-10 object-cover rounded border border-purple-300 shadow-2xs flex-shrink-0 bg-slate-100"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
          ) : (
            <div className="w-10 h-10 rounded bg-pink-100 flex items-center justify-center text-pink-600 flex-shrink-0">
              <Camera className="w-5 h-5" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-1">
              <span className="text-[10px] uppercase font-bold tracking-wider text-pink-700 flex items-center gap-1">
                <Camera className="w-3 h-3" /> Photo
              </span>
              {isCrossApp && (
                <span className="text-[9px] bg-purple-600 text-white font-bold px-1.5 py-0.5 rounded-full shadow-2xs">
                  {occurrenceCount} apps
                </span>
              )}
            </div>
            <div className="text-xs font-bold text-slate-900 truncate">
              {String(nodeData.label || 'Lab Photo')}
            </div>
            {isCrossApp && (
              <div className="text-[10px] text-purple-700 font-semibold truncate">
                Duplicate Photo
              </div>
            )}
          </div>
        </div>
      ) : (
        <div>
          <div className="flex items-center justify-between gap-1 mb-1">
            <div className="flex items-center gap-1.5">
              {getIcon()}
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
                {String(nodeData.entity_type || 'entity').replace('_', ' ')}
              </span>
            </div>
            {isCrossApp && (
              <span className="text-[9px] bg-purple-600 text-white font-bold px-1.5 py-0.5 rounded-full shadow-2xs flex-shrink-0">
                Multi-App Match ({occurrenceCount})
              </span>
            )}
          </div>
          <div className="text-xs font-bold text-slate-900 truncate" title={String(nodeData.label || '')}>
            {String(nodeData.label || '')}
          </div>
        </div>
      )}

      {/* Source handle on Right */}
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        className={`!w-2.5 !h-2.5 !border-white !border-2 ${isCrossApp ? '!bg-purple-600' : '!bg-slate-400'}`}
      />
    </div>
  );
};

const nodeTypes = {
  appNode: ApplicationNode,
  entityNode: EntityCustomNode,
};

interface EntityGraphProps {
  applicationId?: number;
}

export const EntityGraph: React.FC<EntityGraphProps> = ({ applicationId }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  const [rawGraphData, setRawGraphData] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [showAllEntities, setShowAllEntities] = useState<boolean>(false);
  const [selectedEntity, setSelectedEntity] = useState<SelectedEntity | null>(null);

  // Fetch raw graph data from API
  const fetchGraphData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getEntityGraph(applicationId);
      setRawGraphData(data || { nodes: [], edges: [] });
    } catch (err) {
      console.error('Error fetching entity graph:', err);
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  // Compute layout & filtered graph whenever rawGraphData or showAllEntities changes
  useEffect(() => {
    if (!rawGraphData.nodes || rawGraphData.nodes.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const allRawNodes = rawGraphData.nodes;
    const allRawEdges = rawGraphData.edges;

    // Filter entities: default is shared only (>= 2 applications)
    let filteredEntityNodes = allRawNodes.filter((n: any) => n.type === 'entity');

    if (!showAllEntities && applicationId !== undefined) {
      filteredEntityNodes = filteredEntityNodes.filter(
        (n: any) => n.data?.is_shared || (n.data?.occurrences && n.data.occurrences.length > 1)
      );
    }

    const activeEntityIds = new Set(filteredEntityNodes.map((n: any) => n.id));

    // Filter application nodes:
    // Focus application is always included.
    // Related applications are included if they connect to at least one active entity.
    const allAppNodes = allRawNodes.filter((n: any) => n.type === 'application');
    let activeAppNodes = allAppNodes;

    if (!showAllEntities && applicationId !== undefined) {
      const activeAppIds = new Set<string>();
      activeAppIds.add(`app-${applicationId}`);

      allRawEdges.forEach((e: any) => {
        if (activeEntityIds.has(e.source) && e.target.startsWith('app-')) {
          activeAppIds.add(e.target);
        } else if (activeEntityIds.has(e.target) && e.source.startsWith('app-')) {
          activeAppIds.add(e.source);
        }
      });

      activeAppNodes = allAppNodes.filter((n: any) => activeAppIds.has(n.id));
    }

    const activeNodeIdSet = new Set([
      ...activeAppNodes.map((n: any) => n.id),
      ...filteredEntityNodes.map((n: any) => n.id),
    ]);

    // Layout positioning to ensure strictly non-crossing left-to-right edges
    const focusApp = activeAppNodes.find((n: any) => n.data?.is_focus);
    const relatedApps = activeAppNodes.filter((n: any) => !n.data?.is_focus);

    // Group entities by related application to place them in non-overlapping blocks
    const sharedByApp: { [appId: string]: any[] } = {};
    relatedApps.forEach((appNode: any) => {
      sharedByApp[appNode.id] = [];
    });
    const unsharedEntities: any[] = [];

    filteredEntityNodes.forEach((entNode: any) => {
      const occs = entNode.data?.occurrences || [];
      const otherOcc = occs.find((o: any) => o.application_id !== applicationId);
      if (otherOcc && sharedByApp[`app-${otherOcc.application_id}`]) {
        sharedByApp[`app-${otherOcc.application_id}`].push(entNode);
      } else {
        unsharedEntities.push(entNode);
      }
    });

    // Calculate Y positions
    let currY = 50;
    const yStep = 80;
    const entityPositions: { [id: string]: { x: number; y: number } } = {};
    const appPositions: { [id: string]: { x: number; y: number } } = {};

    relatedApps.forEach((relApp: any) => {
      const grp = sharedByApp[relApp.id] || [];
      if (grp.length > 0) {
        const startY = currY;
        grp.forEach((ent: any) => {
          entityPositions[ent.id] = { x: 420, y: currY };
          currY += yStep;
        });
        const endY = currY - yStep;
        appPositions[relApp.id] = { x: 840, y: Math.round((startY + endY) / 2) };
        currY += 40; // spacing between groups
      } else {
        appPositions[relApp.id] = { x: 840, y: currY };
        currY += yStep + 20;
      }
    });

    const sharedBlockEndY = currY;

    // Position unshared entities
    unsharedEntities.forEach((ent: any) => {
      entityPositions[ent.id] = { x: 420, y: currY };
      currY += yStep;
    });

    // Position focus application on left
    if (focusApp) {
      const midY =
        relatedApps.length > 0
          ? Math.max(60, Math.round((50 + sharedBlockEndY - 40) / 2))
          : Math.max(60, Math.round((currY - yStep) / 2));
      appPositions[focusApp.id] = { x: 60, y: midY };
    }

    // Assemble final ReactFlow nodes
    const finalNodes = [
      ...activeAppNodes.map((n: any) => ({
        id: n.id,
        type: 'appNode',
        position: appPositions[n.id] || n.position || { x: 60, y: 100 },
        data: n.data,
      })),
      ...filteredEntityNodes.map((n: any) => ({
        id: n.id,
        type: 'entityNode',
        position: entityPositions[n.id] || n.position || { x: 420, y: 100 },
        data: n.data,
      })),
    ];

    // Filter and style edges:
    // Only keep edges connecting active nodes.
    // Shared entities get purple highlight, custom labels, and clean Left-to-Right routing.
    const finalEdges = allRawEdges
      .filter((e: any) => activeNodeIdSet.has(e.source) && activeNodeIdSet.has(e.target))
      .map((edge: any) => {
        const isShared = Boolean(edge.is_shared);

        return {
          id: edge.id,
          source: edge.source,
          sourceHandle: 'right',
          target: edge.target,
          targetHandle: 'left',
          label: edge.label || 'connected',
          type: 'smoothstep',
          style: {
            stroke: isShared ? '#9333ea' : '#94a3b8',
            strokeWidth: isShared ? 2.2 : 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 14,
            height: 14,
            color: isShared ? '#9333ea' : '#94a3b8',
          },
          labelStyle: {
            fill: isShared ? '#6b21a8' : '#475569',
            fontSize: 10,
            fontWeight: 700,
          },
          labelBgStyle: {
            fill: isShared ? '#f3e8ff' : '#ffffff',
            stroke: isShared ? '#c084fc' : '#cbd5e1',
            strokeWidth: 1,
            rx: 4,
            ry: 4,
          },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 4,
        };
      });

    setNodes(finalNodes);
    setEdges(finalEdges);
  }, [rawGraphData, showAllEntities, applicationId, setNodes, setEdges]);

  const onNodeClick = (_: React.MouseEvent, node: any) => {
    if (node.type === 'entityNode') {
      setSelectedEntity({
        id: node.id,
        label: node.data.label,
        entity_type: node.data.entity_type,
        thumbnail_url: node.data.thumbnail_url,
        occurrences: node.data.occurrences || [],
      });
    }
  };

  const entityStats = useMemo(() => {
    const rawEntities = (rawGraphData.nodes || []).filter((n: any) => n.type === 'entity');
    const total = rawEntities.length;
    const shared = rawEntities.filter(
      (n: any) => n.data?.is_shared || (n.data?.occurrences && n.data.occurrences.length > 1)
    ).length;
    return { total, shared };
  }, [rawGraphData]);

  return (
    <div className="relative w-full h-[640px] bg-slate-50 border border-slate-200 rounded-lg overflow-hidden flex flex-col shadow-xs">
      {/* Top Banner / Toolbar */}
      <div className="bg-white border-b border-slate-200 px-4 py-2.5 flex items-center justify-between text-xs text-slate-700 z-10 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <span className="font-bold text-slate-900 flex items-center gap-1.5">
            <Users className="w-4 h-4 text-purple-700" />
            Cross-Application Entity Relationship Graph
          </span>
          <span className="text-slate-300">|</span>
          <span className="text-slate-500 hidden md:inline">
            Links read left-to-right from current application to shared entities and connected institutions
          </span>
        </div>

        {/* Controls & Legend */}
        <div className="flex items-center gap-4 text-[11px]">
          {/* Toggle "Show all entities" */}
          <label className="inline-flex items-center gap-2 cursor-pointer select-none bg-slate-50 hover:bg-slate-100 px-2.5 py-1 rounded-md border border-slate-300 transition-colors">
            <input
              type="checkbox"
              checked={showAllEntities}
              onChange={(e) => setShowAllEntities(e.target.checked)}
              className="w-3.5 h-3.5 text-purple-600 rounded border-slate-300 focus:ring-purple-500 cursor-pointer accent-purple-600"
            />
            <span className="text-xs font-semibold text-slate-700 flex items-center gap-1">
              <Filter className="w-3 h-3 text-slate-500" />
              Show all entities
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-slate-200 text-slate-700">
              {showAllEntities ? entityStats.total : entityStats.shared}
            </span>
          </label>

          <div className="h-4 w-px bg-slate-200" />

          {/* Legend */}
          <div className="flex items-center gap-3 text-[11px]">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span> High Risk
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Medium Risk
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Low Risk
            </span>
            <span className="flex items-center gap-1.5 font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded border border-purple-200">
              <span className="w-2.5 h-2.5 rounded bg-purple-600"></span> Multi-App Match
            </span>
          </div>
        </div>
      </div>

      {/* Main Flow Canvas */}
      <div className="relative flex-1 w-full h-full">
        {loading ? (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-purple-700 mr-2"></div>
            Loading entity graph...
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            minZoom={0.2}
            maxZoom={2}
          >
            <Background gap={18} size={1} color="#cbd5e1" />
            <Controls position="bottom-left" />
          </ReactFlow>
        )}

        {/* Selected Entity Slideover Details */}
        {selectedEntity && (
          <div className="absolute top-0 right-0 w-96 h-full bg-white border-l border-slate-300 shadow-2xl p-5 overflow-y-auto z-20 flex flex-col animate-in slide-in-from-right duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <span className="p-2 rounded-lg bg-purple-100 text-purple-700">
                  {selectedEntity.entity_type === 'faculty' && <Users className="w-5 h-5" />}
                  {selectedEntity.entity_type === 'fire_noc_no' && <Flame className="w-5 h-5" />}
                  {selectedEntity.entity_type === 'deed_no' && <FileText className="w-5 h-5" />}
                  {selectedEntity.entity_type === 'survey_no' && <MapPin className="w-5 h-5" />}
                  {(selectedEntity.entity_type === 'photo' || selectedEntity.entity_type === 'photo_hash') && (
                    <Camera className="w-5 h-5" />
                  )}
                </span>
                <div>
                  <div className="text-[10px] uppercase font-bold tracking-wider text-purple-700">
                    {selectedEntity.entity_type.replace('_', ' ')}
                  </div>
                  <h3 className="font-bold text-slate-900 text-sm truncate max-w-[210px]" title={selectedEntity.label}>
                    {selectedEntity.label}
                  </h3>
                </div>
              </div>
              <button
                onClick={() => setSelectedEntity(null)}
                className="text-slate-400 hover:text-slate-700 p-1.5 rounded-md hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 flex-1">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-slate-800">
                  Connected Applications ({selectedEntity.occurrences.length})
                </span>
                {selectedEntity.occurrences.length > 1 && (
                  <span className="text-[10px] font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-full flex items-center gap-1 border border-purple-200">
                    <AlertCircle className="w-3 h-3 text-purple-700" /> Multi-App Match
                  </span>
                )}
              </div>

              {selectedEntity.occurrences.length === 0 ? (
                <div className="text-xs text-slate-500 italic p-3 bg-slate-50 rounded">
                  No occurrence records details found.
                </div>
              ) : (
                <div className="space-y-3">
                  {selectedEntity.occurrences.map((occ, idx) => (
                    <div
                      key={idx}
                      className="border border-slate-200 rounded-lg p-3 bg-slate-50/70 hover:bg-slate-100/70 transition-colors shadow-2xs"
                    >
                      <div className="flex items-center justify-between text-xs font-bold text-slate-900 mb-1.5">
                        <span className="flex items-center gap-1.5">
                          <Building2 className="w-3.5 h-3.5 text-slate-500" />
                          <span>{occ.institution_id || `App #${occ.application_id}`}</span>
                          {occ.risk_band && (
                            <span
                              className={`text-[9px] font-bold px-1.5 py-0.2 rounded text-white ${
                                occ.risk_band === 'High'
                                  ? 'bg-red-600'
                                  : occ.risk_band === 'Medium'
                                  ? 'bg-amber-600'
                                  : 'bg-emerald-600'
                              }`}
                            >
                              {occ.risk_band}
                            </span>
                          )}
                        </span>
                        <a
                          href={`/applications/${occ.application_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-purple-700 hover:text-purple-900 hover:underline flex items-center gap-0.5 text-[11px] font-semibold"
                        >
                          Open <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>

                      <div className="text-[11px] text-slate-600 space-y-0.5">
                        {occ.institution_name && (
                          <div className="text-slate-800 font-medium truncate">
                            {occ.institution_name}
                          </div>
                        )}
                        <div>
                          <span className="font-medium text-slate-700">Document:</span>{' '}
                          {occ.doc_type || 'Declared entity'}
                        </div>
                        {occ.academic_year && (
                          <div>
                            <span className="font-medium text-slate-700">Academic Year:</span>{' '}
                            {occ.academic_year}
                          </div>
                        )}
                      </div>

                      {occ.thumbnail_url && (
                        <div className="mt-2.5 pt-2 border-t border-slate-200">
                          <div className="text-[10px] font-bold text-slate-600 mb-1 flex items-center gap-1">
                            <Camera className="w-3 h-3 text-purple-600" />
                            Campus Photo:
                          </div>
                          <img
                            src={occ.thumbnail_url}
                            alt="Photo occurrence"
                            className="w-full h-32 object-cover rounded-md border border-slate-300 shadow-2xs"
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
