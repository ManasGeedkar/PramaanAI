import React, { useState, useRef, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Flame,
  FileText,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { api } from '../api/client';

// Configure pdfjs worker to local static file
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

export interface BoundingBox {
  bbox: [number, number, number, number]; // [x0, y0, x1, y1] in PDF points (595.28pt basis)
  field?: string;
  value?: string;
  label?: string;
}

interface DocumentViewerProps {
  documentId: number;
  docType: string;
  filePath?: string;
  initialPage?: number;
  highlightBoxes?: BoundingBox[];
  enableElaToggle?: boolean;
  elaHeatmapUrl?: string | null;
  onPageChange?: (page: number) => void;
  title?: string;
  zoomTrigger?: any;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  documentId,
  docType,
  filePath,
  initialPage = 1,
  highlightBoxes = [],
  enableElaToggle = false,
  elaHeatmapUrl,
  onPageChange,
  title,
  zoomTrigger,
}) => {
  const [numPages, setNumPages] = useState<number>(1);
  const [pageNumber, setPageNumber] = useState<number>(initialPage);
  const [scaleFactor, setScaleFactor] = useState<number>(1.0);
  const [showEla, setShowEla] = useState<boolean>(false);
  const [elaOpacity, setElaOpacity] = useState<number>(0.85);
  const [containerWidth, setContainerWidth] = useState<number>(600);
  const [pdfLoadError, setPdfLoadError] = useState<string | null>(null);
  const [originalPageWidth, setOriginalPageWidth] = useState<number>(595.28);
  const [isPdfLoading, setIsPdfLoading] = useState<boolean>(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const activeBoxRef = useRef<HTMLDivElement>(null);

  const isImage =
    docType?.startsWith('photo:') ||
    filePath?.toLowerCase().endsWith('.jpg') ||
    filePath?.toLowerCase().endsWith('.jpeg') ||
    filePath?.toLowerCase().endsWith('.png');

  // Update page when initialPage changes
  useEffect(() => {
    if (initialPage && initialPage !== pageNumber) {
      setPageNumber(initialPage);
    }
  }, [initialPage]);

  // Measure container width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        const measured = containerRef.current.clientWidth - 48; // padding
        if (measured > 200) {
          setContainerWidth(measured);
        }
      }
    };

    updateWidth();
    const ro = new ResizeObserver(updateWidth);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Center viewport on the evidence box with guaranteed full visibility of the right-hand label
  const centerOnBox = () => {
    const container = scrollContainerRef.current;
    const box = activeBoxRef.current;
    if (!container || !box) return;

    try {
      // 1. Center the bounding box vertically & horizontally
      box.scrollIntoView({ behavior: 'auto', block: 'center', inline: 'center' });

      // 2. Adjust horizontal scroll to guarantee ample right margin for the label
      const containerRect = container.getBoundingClientRect();
      const boxRect = box.getBoundingClientRect();
      const labelEl = box.querySelector('div');
      const labelWidth = labelEl ? labelEl.getBoundingClientRect().width : 160;

      // Label right edge relative to container viewport
      const labelRight = boxRect.left + boxRect.width + labelWidth;
      const safeRightLimit = containerRect.right - 90; // 90px right safety margin

      if (labelRight > safeRightLimit) {
        container.scrollLeft += labelRight - safeRightLimit;
      }
    } catch (e) {
      // fallback
    }
  };

  // When a finding is selected (highlightBoxes present/changed or zoomTrigger changed),
  // auto-zoom to 200% (scaleFactor = 2.0) and center the viewport on the evidence box!
  useEffect(() => {
    if (highlightBoxes.length > 0) {
      setScaleFactor(2.0);

      const t1 = setTimeout(centerOnBox, 100);
      const t2 = setTimeout(centerOnBox, 300);
      const t3 = setTimeout(centerOnBox, 600);
      const t4 = setTimeout(centerOnBox, 1000);
      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
        clearTimeout(t4);
      };
    }
  }, [highlightBoxes, pageNumber, zoomTrigger]);

  const fileUrl = api.getDocumentFileUrl(documentId);
  const elaUrl = elaHeatmapUrl || api.getDocumentElaUrl(documentId);

  const handleDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setIsPdfLoading(false);
    setPdfLoadError(null);
  };

  const handleDocumentLoadError = (err: Error) => {
    setPdfLoadError(err.message);
    setIsPdfLoading(false);
  };

  const handlePageLoadSuccess = (page: any) => {
    const origWidth = page.originalWidth || 595.28;
    setOriginalPageWidth(origWidth);
  };

  const changePage = (offset: number) => {
    const newPage = Math.min(Math.max(1, pageNumber + offset), numPages);
    setPageNumber(newPage);
    if (onPageChange) onPageChange(newPage);
  };

  // Rendered width for the page canvas
  const renderedWidth = Math.max(300, Math.floor(containerWidth * scaleFactor));
  // Scale factor: PDF points (default standard 595.28) to rendered screen pixels
  const pointScale = renderedWidth / (originalPageWidth || 595.28);

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full bg-slate-900/5 rounded-xl border border-slate-200 overflow-hidden"
    >
      {/* Top Controls Toolbar */}
      <div className="bg-slate-800 text-white px-4 py-2 flex flex-wrap items-center justify-between gap-2.5 text-xs border-b border-slate-700 flex-shrink-0">
        <div className="flex items-center gap-2 font-medium">
          <FileText className="w-4 h-4 text-slate-400" />
          <span className="font-semibold text-slate-100">{title || docType}</span>
          {!isImage && numPages > 1 && (
            <span className="text-[11px] text-slate-400">
              (Page {pageNumber} of {numPages})
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* ELA Heatmap Toggle (for TAMPER_SUSPECTED) */}
          {enableElaToggle && (
            <div className="flex items-center gap-2 bg-slate-900/80 px-2 py-0.5 rounded-md border border-slate-700">
              <button
                id="toggle-ela-heatmap"
                onClick={() => setShowEla(!showEla)}
                className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold transition-all ${
                  showEla
                    ? 'bg-amber-500 text-slate-950 shadow-xs'
                    : 'bg-slate-800 text-amber-300 hover:bg-slate-700'
                }`}
                title="Overlay Error Level Analysis heatmap"
              >
                <Flame className="w-3.5 h-3.5" />
                <span>{showEla ? 'Hide ELA' : 'Show ELA Heatmap'}</span>
              </button>

              {showEla && (
                <div className="flex items-center gap-1 text-[11px] text-slate-300">
                  <span className="text-[10px]">Opacity:</span>
                  <input
                    type="range"
                    min="0.2"
                    max="1.0"
                    step="0.05"
                    value={elaOpacity}
                    onChange={(e) => setElaOpacity(parseFloat(e.target.value))}
                    className="w-14 h-1 bg-slate-700 accent-amber-400 cursor-pointer"
                  />
                  <span className="font-mono text-[10px] w-6">{Math.round(elaOpacity * 100)}%</span>
                </div>
              )}
            </div>
          )}

          {/* Zoom Controls */}
          <div className="flex items-center gap-1 bg-slate-900/60 px-1.5 py-0.5 rounded-md border border-slate-700">
            <button
              onClick={() => setScaleFactor((prev) => Math.max(0.6, prev - 0.2))}
              className="p-1 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors"
              title="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="font-mono text-[11px] text-slate-300 px-1 min-w-[38px] text-center">
              {Math.round(scaleFactor * 100)}%
            </span>
            <button
              onClick={() => setScaleFactor((prev) => Math.min(3.0, prev + 0.2))}
              className="p-1 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setScaleFactor(1.0)}
              className="p-1 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors"
              title="Reset zoom to 100%"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>

          {/* Page Navigation Controls */}
          {!isImage && numPages > 1 && (
            <div className="flex items-center gap-1 bg-slate-900/60 px-1.5 py-0.5 rounded-md border border-slate-700">
              <button
                onClick={() => changePage(-1)}
                disabled={pageNumber <= 1}
                className="p-1 text-slate-300 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent hover:bg-slate-700 rounded transition-colors"
                title="Previous page"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="text-[11px] font-mono text-slate-200 px-1.5">
                {pageNumber} / {numPages}
              </span>
              <button
                onClick={() => changePage(1)}
                disabled={pageNumber >= numPages}
                className="p-1 text-slate-300 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent hover:bg-slate-700 rounded transition-colors"
                title="Next page"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Document Canvas Scroll Area */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-auto p-4 bg-slate-200/80 min-h-[480px]"
      >
        <div className="w-fit mx-auto min-w-full flex justify-center pr-32">
          {isImage ? (
            // Photo/Image Viewer
            <div className="relative inline-block bg-white rounded shadow-lg border border-slate-300">
              <img
                src={fileUrl}
                alt={docType}
                style={{ width: `${renderedWidth}px` }}
                className="block object-contain"
              />
            {/* Image highlight boxes if any */}
            {highlightBoxes.map((box, idx) => {
              const [x0, y0, x1, y1] = box.bbox;
              const left = x0 * pointScale;
              const top = y0 * pointScale;
              const width = (x1 - x0) * pointScale;
              const height = (y1 - y0) * pointScale;
              const hasRoomOnRight = left + width + 170 < renderedWidth;

              return (
                <div
                  key={idx}
                  ref={idx === 0 ? activeBoxRef : null}
                  id={`highlight-box-${idx}`}
                  className="absolute border-2 border-red-600 bg-red-500/20 shadow-[0_0_12px_rgba(239,68,68,0.55)] ring-2 ring-red-400/40 z-20 pointer-events-auto"
                  style={{
                    left: `${left}px`,
                    top: `${top}px`,
                    width: `${Math.max(width, 12)}px`,
                    height: `${Math.max(height, 10)}px`,
                  }}
                >
                  {/* Position label to the right of the box; if no room, below. NEVER above! */}
                  <div
                    className={`absolute bg-red-600 text-white font-mono text-[10px] font-bold px-1.5 py-0.5 rounded shadow z-30 whitespace-nowrap pointer-events-none flex items-center gap-1 ${
                      hasRoomOnRight
                        ? 'left-full top-0 ml-1.5'
                        : 'top-full left-0 mt-1'
                    }`}
                  >
                    <span>{box.field ? `${box.field}: ` : ''}{box.value || 'Evidence'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          // PDF Viewer via react-pdf
          <div className="relative inline-block bg-white rounded-md shadow-xl border border-slate-300">
            {isPdfLoading && (
              <div className="absolute inset-0 bg-white/80 z-40 flex items-center justify-center p-8 text-slate-500 gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-blue-700" />
                <span className="text-xs font-medium">Rendering PDF page...</span>
              </div>
            )}

            {pdfLoadError ? (
              <div className="p-8 text-center text-red-600 text-xs bg-red-50 rounded border border-red-200">
                <AlertCircle className="w-6 h-6 mx-auto mb-2 text-red-500" />
                <p className="font-semibold">Unable to render PDF document</p>
                <p className="text-[11px] text-red-500 mt-1">{pdfLoadError}</p>
              </div>
            ) : (
              <Document
                file={fileUrl}
                onLoadSuccess={handleDocumentLoadSuccess}
                onLoadError={handleDocumentLoadError}
                loading={
                  <div className="p-12 flex items-center justify-center text-slate-400 gap-2">
                    <Loader2 className="w-5 h-5 animate-spin text-blue-700" />
                    <span className="text-xs">Loading PDF document...</span>
                  </div>
                }
              >
                <div className="relative inline-block">
                  <Page
                    pageNumber={pageNumber}
                    width={renderedWidth}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                    onLoadSuccess={handlePageLoadSuccess}
                    onRenderSuccess={centerOnBox}
                  />

                  {/* Red Evidence Bounding Boxes */}
                  {highlightBoxes.map((box, idx) => {
                    const [x0, y0, x1, y1] = box.bbox;
                    const left = x0 * pointScale;
                    const top = y0 * pointScale;
                    const width = (x1 - x0) * pointScale;
                    const height = (y1 - y0) * pointScale;

                    // Place label to the right of the box; if no room, below. NEVER above!
                    const hasRoomOnRight = left + width + 170 < renderedWidth;

                    return (
                      <div
                        key={idx}
                        ref={idx === 0 ? activeBoxRef : null}
                        id={`highlight-box-${idx}`}
                        className="absolute border-2 border-red-600 bg-red-500/20 shadow-[0_0_12px_rgba(220,38,38,0.55)] ring-2 ring-red-500/40 z-20 pointer-events-auto transition-transform"
                        style={{
                          left: `${left}px`,
                          top: `${top}px`,
                          width: `${Math.max(width, 14)}px`,
                          height: `${Math.max(height, 10)}px`,
                        }}
                      >
                        {/* Red evidence badge label placed right or below (never above!) */}
                        <div
                          className={`absolute bg-red-600 text-white font-mono text-[10px] font-bold px-1.5 py-0.5 rounded shadow z-30 whitespace-nowrap pointer-events-none flex items-center gap-1 ${
                            hasRoomOnRight
                              ? 'left-full top-0 ml-1.5'
                              : 'top-full left-0 mt-1'
                          }`}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                          <span>
                            {box.field ? `${box.field}: ` : ''}
                            {box.value || 'Evidence'}
                          </span>
                        </div>
                      </div>
                    );
                  })}

                  {/* ELA Heatmap Overlay (HOT colormap: dark/black = normal, edited patch glows hot) */}
                  {enableElaToggle && showEla && elaUrl && (
                    <div
                      className="absolute inset-0 pointer-events-none mix-blend-screen z-10 transition-opacity"
                      style={{ opacity: elaOpacity }}
                    >
                      <img
                        src={elaUrl}
                        alt="ELA Heatmap Overlay"
                        className="w-full h-full object-fill block"
                      />
                    </div>
                  )}
                </div>
              </Document>
            )}
          </div>
        )}
        </div>
      </div>

      {/* Bottom Info Bar */}
      {enableElaToggle && showEla && (
        <div className="bg-amber-50 px-4 py-2 border-t border-amber-200 text-[11px] text-amber-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>
              <strong>HOT Colormap ELA Overlay Active:</strong> Dark/black = normal document compression.
              The glowing region indicates the single-compressed edited patch.
            </span>
          </div>
          <span className="font-mono text-[10px] text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
            p99 Normalised
          </span>
        </div>
      )}
    </div>
  );
};
