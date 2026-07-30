import React, { useState } from "react";
import { ChevronUp, ChevronDown, Loader2, Inbox } from "lucide-react";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
  minWidth?: string;
  align?: "left" | "center" | "right";
  sticky?: boolean;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  error?: string | null;
  emptyState?: React.ReactNode;
  sort?: { key: string; dir: "asc" | "desc" };
  onSortChange?: (sort: { key: string; dir: "asc" | "desc" }) => void;
  selectable?: boolean;
  selectedIds?: string[];
  onSelectionChange?: (ids: string[]) => void;
  bulkActions?: React.ReactNode;
  pageSize?: number;
  onRowClick?: (row: T) => void;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  rowKey,
  loading = false,
  error = null,
  emptyState,
  sort,
  onSortChange,
  selectable = false,
  selectedIds = [],
  onSelectionChange,
  bulkActions,
  pageSize = 25,
  onRowClick,
  className = "",
}: DataTableProps<T>) {
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.ceil(data.length / pageSize) || 1;
  const paginatedData = data.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const handleSort = (key: string) => {
    if (!onSortChange) return;
    if (sort?.key === key) {
      onSortChange({ key, dir: sort.dir === "asc" ? "desc" : "asc" });
    } else {
      onSortChange({ key, dir: "asc" });
    }
  };

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!onSelectionChange) return;
    if (e.target.checked) {
      onSelectionChange(data.map(rowKey));
    } else {
      onSelectionChange([]);
    }
  };

  const handleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onSelectionChange) return;
    if (selectedIds.includes(id)) {
      onSelectionChange(selectedIds.filter((item) => item !== id));
    } else {
      onSelectionChange([...selectedIds, id]);
    }
  };

  const allSelected = data.length > 0 && selectedIds.length === data.length;
  const isIndeterminate = selectedIds.length > 0 && !allSelected;

  return (
    <div className={`data-table-container flex flex-col w-full bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-xl overflow-hidden shadow-sm ${className}`}>
      {/* Bulk Action Bar */}
      {selectable && selectedIds.length > 0 && (
        <div className="flex items-center justify-between px-4 py-2.5 bg-indigo-950/60 border-b border-indigo-500/30 text-xs text-indigo-200 animate-fadeIn">
          <div className="flex items-center gap-2 font-medium">
            <span>{selectedIds.length} item(s) selected</span>
            <button
              onClick={() => onSelectionChange?.([])}
              className="text-[11px] underline text-indigo-400 hover:text-indigo-300 ml-2"
            >
              Clear selection
            </button>
          </div>
          <div className="flex items-center gap-2">{bulkActions}</div>
        </div>
      )}

      {/* Main Table */}
      <div className="overflow-x-auto w-full">
        <table className="w-full text-left text-xs text-[var(--text-secondary)] border-collapse">
          <thead className="bg-[var(--bg-surface-alt)] border-b border-[var(--border-default)] text-[var(--text-muted)] uppercase tracking-wider text-[10px] font-semibold sticky top-0 z-10">
            <tr>
              {selectable && (
                <th className="p-3 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(input) => {
                      if (input) input.indeterminate = isIndeterminate;
                    }}
                    onChange={handleSelectAll}
                    className="rounded border-[var(--border-default)] bg-[var(--bg-input)] text-indigo-500 focus:ring-0 cursor-pointer"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={{ width: col.width, minWidth: col.minWidth }}
                  className={`p-3 ${col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"} ${
                    col.sortable ? "cursor-pointer select-none hover:text-[var(--text-primary)]" : ""
                  }`}
                  onClick={() => col.sortable && handleSort(col.key)}
                >
                  <div className={`inline-flex items-center gap-1 ${col.align === "right" ? "justify-end" : ""}`}>
                    <span>{col.header}</span>
                    {col.sortable && sort?.key === col.key && (
                      sort.dir === "asc" ? <ChevronUp className="w-3 h-3 text-indigo-400" /> : <ChevronDown className="w-3 h-3 text-indigo-400" />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)]">
            {loading ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="p-12 text-center">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-500 mx-auto mb-2" />
                  <p className="text-xs text-[var(--text-muted)]">Loading items...</p>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="p-8 text-center text-rose-400">
                  <p className="text-xs font-semibold">{error}</p>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="p-12 text-center">
                  {emptyState || (
                    <div className="flex flex-col items-center gap-2 text-[var(--text-muted)]">
                      <Inbox className="w-8 h-8 stroke-[1.5]" />
                      <p className="text-xs font-medium">No records found</p>
                    </div>
                  )}
                </td>
              </tr>
            ) : (
              paginatedData.map((row) => {
                const key = rowKey(row);
                const isSelected = selectedIds.includes(key);
                return (
                  <tr
                    key={key}
                    onClick={() => onRowClick?.(row)}
                    className={`transition-colors ${onRowClick ? "cursor-pointer hover:bg-[var(--bg-card-hover)]" : "hover:bg-[var(--bg-surface-alt)]"} ${
                      isSelected ? "bg-indigo-950/20" : ""
                    }`}
                  >
                    {selectable && (
                      <td className="p-3 text-center" onClick={(e) => handleSelectRow(key, e)}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="rounded border-[var(--border-default)] bg-[var(--bg-input)] text-indigo-500 focus:ring-0 cursor-pointer"
                        />
                      </td>
                    )}
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={`p-3 text-xs text-[var(--text-secondary)] ${
                          col.align === "right" ? "text-right" : col.align === "center" ? "text-center" : "text-left"
                        }`}
                      >
                        {col.render ? col.render(row) : (row as any)[col.key]}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {data.length > pageSize && (
        <div className="flex items-center justify-between px-4 py-3 bg-[var(--bg-surface-alt)] border-t border-[var(--border-default)] text-xs text-[var(--text-muted)]">
          <div>
            Showing {(currentPage - 1) * pageSize + 1} to {Math.min(currentPage * pageSize, data.length)} of {data.length} items
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
              className="px-2.5 py-1 rounded bg-[var(--bg-input)] border border-[var(--border-default)] hover:bg-[var(--bg-elevated)] disabled:opacity-40 text-[11px]"
            >
              Previous
            </button>
            <span className="font-mono text-[11px] text-[var(--text-primary)]">
              {currentPage} / {totalPages}
            </span>
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
              className="px-2.5 py-1 rounded bg-[var(--bg-input)] border border-[var(--border-default)] hover:bg-[var(--bg-elevated)] disabled:opacity-40 text-[11px]"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
