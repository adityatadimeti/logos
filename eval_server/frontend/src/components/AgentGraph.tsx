import { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api';

interface Node {
  id: string;
  label: string;
  type: string;
  x?: number;
  y?: number;
}

interface Edge {
  source: string;
  target: string;
  label: string;
}

interface GraphData {
  nodes: Node[];
  edges: Edge[];
  description: string;
}

export default function AgentGraph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const fetchGraphData = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getAgentGraph();
        
        // Position nodes in a flow layout
        const positionedNodes = positionNodes(data.nodes, data.edges);
        setGraphData({
          ...data,
          nodes: positionedNodes
        });
        setError(null);
      } catch (err) {
        setError('Failed to fetch agent graph');
        console.error('Error fetching agent graph:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchGraphData();
  }, []);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(prev => Math.max(0.1, Math.min(3, prev * zoomFactor)));
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setLastMousePos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    
    const deltaX = e.clientX - lastMousePos.x;
    const deltaY = e.clientY - lastMousePos.y;
    
    setPanX(prev => prev + deltaX);
    setPanY(prev => prev + deltaY);
    setLastMousePos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const zoomIn = () => {
    setZoom(prev => Math.min(3, prev * 1.2));
  };

  const zoomOut = () => {
    setZoom(prev => Math.max(0.1, prev / 1.2));
  };

  const resetView = () => {
    setZoom(1);
    setPanX(0);
    setPanY(0);
  };

  const positionNodes = (nodes: Node[], edges: Edge[]): Node[] => {
    // Create a more spaced-out layout
    const nodeMap = new Map(nodes.map(n => [n.id, { ...n }]));
    
    // Define specific positions for better readability
    const positions: Record<string, { x: number; y: number }> = {
      '__start__': { x: 400, y: 50 },
      'plan_workflow': { x: 400, y: 150 },
      'guardrails': { x: 200, y: 250 },
      'db_agent': { x: 300, y: 350 },
      'viz_agent': { x: 400, y: 350 },
      'web_agent': { x: 500, y: 350 },
      'respond': { x: 400, y: 450 },
      '__end__': { x: 400, y: 550 }
    };
    
    // Apply positions or use automatic positioning for unknown nodes
    nodes.forEach(node => {
      const mapNode = nodeMap.get(node.id);
      if (mapNode) {
        if (positions[node.id]) {
          mapNode.x = positions[node.id].x;
          mapNode.y = positions[node.id].y;
        } else {
          // Fallback positioning for unknown nodes
          const index = nodes.findIndex(n => n.id === node.id);
          mapNode.x = 100 + (index % 5) * 150;
          mapNode.y = 100 + Math.floor(index / 5) * 100;
        }
      }
    });
    
    return Array.from(nodeMap.values());
  };

  const getNodeColor = (type: string) => {
    switch (type) {
      case 'agent':
        return '#4f46e5'; // Purple for agents
      case 'control':
        return '#06b6d4'; // Teal for control nodes
      default:
        return '#6b7280'; // Gray for others
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
        Loading agent graph...
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <h3>Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!graphData) {
    return (
      <div className="empty-state">
        <h3>No Graph Data</h3>
        <p>Unable to load agent graph structure.</p>
      </div>
    );
  }

  return (
    <>
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '8px' }}>
          <div style={{
            width: '48px',
            height: '48px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '24px',
            fontWeight: 'bold',
            color: 'white',
            letterSpacing: '-1px'
          }}>
            Λ
          </div>
          <div>
            <h1 style={{ 
              margin: 0, 
              fontSize: '28px', 
              fontWeight: '700',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}>
              Agent Workflow Graph
            </h1>
            <p style={{ 
              margin: '4px 0 0 0', 
              fontSize: '16px', 
              color: 'var(--muted)',
              fontWeight: '400'
            }}>
              {graphData.description}
            </p>
          </div>
        </div>
      </header>

      <div className="card">
        <div className="card-header">
          <h2>LangGraph Visualization</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ fontSize: '14px', color: 'var(--muted)' }}>
              {graphData.nodes.length} nodes, {graphData.edges.length} edges
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button onClick={zoomOut} className="btn btn-secondary" title="Zoom Out">
                ➖
              </button>
              <span style={{ fontSize: '12px', color: 'var(--muted)', minWidth: '60px', textAlign: 'center' }}>
                {Math.round(zoom * 100)}%
              </span>
              <button onClick={zoomIn} className="btn btn-secondary" title="Zoom In">
                ➕
              </button>
              <button onClick={resetView} className="btn btn-secondary" title="Reset View">
                🔄
              </button>
            </div>
          </div>
        </div>
        <div className="card-body">
          <div style={{
            width: '100%',
            height: '600px',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            background: 'var(--bg)',
            overflow: 'hidden',
            position: 'relative',
            cursor: isDragging ? 'grabbing' : 'grab'
          }}>
            <svg
              ref={svgRef}
              width="100%"
              height="100%"
              viewBox="0 0 800 600"
              style={{ background: 'rgba(15, 16, 32, 0.3)' }}
              onWheel={handleWheel}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              {/* Transform group for zoom and pan */}
              <g transform={`translate(${panX}, ${panY}) scale(${zoom})`}>
              {/* Define arrow marker */}
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="10"
                  markerHeight="7"
                  refX="9"
                  refY="3.5"
                  orient="auto"
                >
                  <polygon
                    points="0 0, 10 3.5, 0 7"
                    fill="var(--muted)"
                  />
                </marker>
              </defs>

              {/* Render edges */}
              {graphData.edges.map((edge, index) => {
                const sourceNode = graphData.nodes.find(n => n.id === edge.source);
                const targetNode = graphData.nodes.find(n => n.id === edge.target);
                
                if (!sourceNode || !targetNode || !sourceNode.x || !sourceNode.y || !targetNode.x || !targetNode.y) {
                  return null;
                }

                // Calculate control points for curved path
                const deltaX = targetNode.x - sourceNode.x;
                const deltaY = targetNode.y - sourceNode.y;
                const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
                
                // Create curve based on direction
                let controlX1, controlY1, controlX2, controlY2;
                
                if (Math.abs(deltaX) > Math.abs(deltaY)) {
                  // Horizontal curve
                  const curve = Math.min(distance * 0.3, 50);
                  controlX1 = sourceNode.x + deltaX * 0.3;
                  controlY1 = sourceNode.y - curve * Math.sign(deltaX);
                  controlX2 = targetNode.x - deltaX * 0.3;
                  controlY2 = targetNode.y - curve * Math.sign(deltaX);
                } else {
                  // Vertical curve
                  const curve = Math.min(distance * 0.2, 40);
                  controlX1 = sourceNode.x + curve * (deltaX > 0 ? 1 : -1);
                  controlY1 = sourceNode.y + deltaY * 0.3;
                  controlX2 = targetNode.x - curve * (deltaX > 0 ? 1 : -1);
                  controlY2 = targetNode.y - deltaY * 0.3;
                }

                const pathData = `M ${sourceNode.x} ${sourceNode.y} C ${controlX1} ${controlY1}, ${controlX2} ${controlY2}, ${targetNode.x} ${targetNode.y}`;
                
                // Calculate label position along the curve (at t=0.5)
                const labelX = (sourceNode.x + 3 * controlX1 + 3 * controlX2 + targetNode.x) / 8;
                const labelY = (sourceNode.y + 3 * controlY1 + 3 * controlY2 + targetNode.y) / 8;

                return (
                  <g key={index}>
                    {/* Curved path */}
                    <path
                      d={pathData}
                      stroke="var(--muted)"
                      strokeWidth="2"
                      fill="none"
                      markerEnd="url(#arrowhead)"
                      opacity="0.6"
                    />
                    {/* Edge label with background */}
                    <circle
                      cx={labelX}
                      cy={labelY}
                      r="12"
                      fill="var(--bg)"
                      stroke="var(--border)"
                      strokeWidth="1"
                      opacity="0.9"
                    />
                    <text
                      x={labelX}
                      y={labelY + 3}
                      fill="var(--text)"
                      fontSize="8"
                      textAnchor="middle"
                      fontWeight="500"
                      opacity="0.8"
                    >
                      {edge.target.split('_')[0]}
                    </text>
                  </g>
                );
              })}

              {/* Render nodes */}
              {graphData.nodes.map((node) => {
                if (!node.x || !node.y) return null;
                
                const nodeColor = getNodeColor(node.type);
                const radius = 35;
                
                return (
                  <g key={node.id}>
                    {/* Node background circle */}
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={radius + 2}
                      fill="var(--bg)"
                      stroke="var(--border)"
                      strokeWidth="1"
                      opacity="0.8"
                    />
                    {/* Node circle */}
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={radius}
                      fill={nodeColor}
                      stroke="white"
                      strokeWidth="2"
                      opacity="0.9"
                    />
                    {/* Node type indicator */}
                    <text
                      x={node.x}
                      y={node.y + 6}
                      fill="white"
                      fontSize="16"
                      textAnchor="middle"
                      fontWeight="600"
                    >
                      {node.type === 'agent' ? '🤖' : '⚙️'}
                    </text>
                    {/* Node label background */}
                    <rect
                      x={node.x - 50}
                      y={node.y + radius + 8}
                      width="100"
                      height="20"
                      fill="var(--bg)"
                      stroke="var(--border)"
                      strokeWidth="1"
                      rx="4"
                      opacity="0.9"
                    />
                    {/* Node label */}
                    <text
                      x={node.x}
                      y={node.y + radius + 22}
                      fill="var(--text)"
                      fontSize="11"
                      textAnchor="middle"
                      fontWeight="600"
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
              </g>
            </svg>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="card">
        <div className="card-header">
          <h2>Legend & Controls</h2>
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <div>
              <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: '600' }}>Node Types</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    backgroundColor: '#4f46e5'
                  }}></div>
                  <span>🤖 Agent Nodes (DB, Viz, Web)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    backgroundColor: '#06b6d4'
                  }}></div>
                  <span>⚙️ Control Nodes (Planning, Guardrails, Response)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '20px',
                    height: '2px',
                    backgroundColor: 'var(--muted)'
                  }}></div>
                  <span>→ Workflow Flow</span>
                </div>
              </div>
            </div>
            
            <div>
              <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: '600' }}>Navigation</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', color: 'var(--muted)' }}>
                <div>• <strong>Mouse Wheel:</strong> Zoom in/out</div>
                <div>• <strong>Click & Drag:</strong> Pan around</div>
                <div>• <strong>Zoom Buttons:</strong> Precise zoom control</div>
                <div>• <strong>Reset Button:</strong> Return to default view</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
