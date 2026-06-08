'use client';

import * as React from 'react';
import {cx, applyCommonProps, invariant, useStableId} from './common';
// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TreeItemData {
  id: string;
  label: string;
  children?: TreeItemData[];
}

interface TreeBaseProps
  extends Omit<
      React.ComponentPropsWithoutRef<'div'>,
      'className' | 'style' | 'onSelect'
    > {
  /** Tree data to render. */
  data: TreeItemData[];
  /** IDs expanded by default. */
  defaultExpandedIds?: string[];
  /** Callback when a node is selected. */
  onSelect?: (id: string) => void;
  /** Currently selected node ID. */
  selectedId?: string;
}

type TreeWithLabel = TreeBaseProps & {
  /** Visible label for the tree. */
  label: string;
  a11yLabelledBy?: never;
};

type TreeWithA11yLabel = TreeBaseProps & {
  label?: never;
  /** ID of external label element. */
  a11yLabelledBy: string;
};

export type TreeProps = TreeWithLabel | TreeWithA11yLabel;

// ---------------------------------------------------------------------------
// TreeNode (internal)
// ---------------------------------------------------------------------------

interface TreeNodeProps {
  node: TreeItemData;
  depth: number;
  expandedIds: Set<string>;
  selectedId?: string;
  onToggle: (id: string) => void;
  onSelect?: (id: string) => void;
}

function TreeNode({node, depth, expandedIds, selectedId, onToggle, onSelect}: TreeNodeProps) {
  const hasChildren = node.children && node.children.length > 0;
  const isExpanded = expandedIds.has(node.id);
  const isSelected = selectedId === node.id;

  const handleClick = () => {
    if (hasChildren) {
      onToggle(node.id);
    }
    onSelect?.(node.id);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <li
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-selected={isSelected}
    >
      <div
        className={cx(
          'ld-tree-node',
          isSelected && 'ld-tree-node--selected'
        )}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        style={{paddingLeft: `${depth * 1.5 + 0.5}rem`}}
      >
        <span className="ld-tree-node-toggle" aria-hidden="true">
          {hasChildren ? (
            <svg
              className={cx('ld-tree-node-chevron', isExpanded && 'ld-tree-node-chevron--expanded')}
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="currentColor"
            >
              <path d="M6 3l5 5-5 5z" />
            </svg>
          ) : (
            <span className="ld-tree-node-spacer" />
          )}
        </span>
        <span className="ld-tree-node-label">{node.label}</span>
      </div>
      {hasChildren && isExpanded && (
        <ul role="group" className="ld-tree-group">
          {node.children!.map(child => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              expandedIds={expandedIds}
              selectedId={selectedId}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Tree
// ---------------------------------------------------------------------------

export const Tree = React.forwardRef<HTMLDivElement, TreeProps>(
  (props, ref) => {
    const {
      a11yLabelledBy,
      className,
      data,
      defaultExpandedIds = [],
      label,
      onSelect,
      selectedId,
      ...rest
    } = applyCommonProps(props);

    const id = useStableId();

    invariant(
      !!(label || a11yLabelledBy),
      'Tree requires either a `label` or `a11yLabelledBy` prop for accessibility.'
    );

    const [expandedIds, setExpandedIds] = React.useState<Set<string>>(
      () => new Set(defaultExpandedIds)
    );

    const handleToggle = React.useCallback((nodeId: string) => {
      setExpandedIds(prev => {
        const next = new Set(prev);
        if (next.has(nodeId)) {
          next.delete(nodeId);
        } else {
          next.add(nodeId);
        }
        return next;
      });
    }, []);

    const classes = cx('ld-tree', className);

    return (
      <div className={classes} ref={ref} {...rest}>
        {label && (
          <div className="ld-tree-label" id={`${id}-label`}>
            {label}
          </div>
        )}
        <ul
          role="tree"
          aria-labelledby={a11yLabelledBy || (label ? `${id}-label` : undefined)}
          className="ld-tree-root"
        >
          {data.map(node => (
            <TreeNode
              key={node.id}
              node={node}
              depth={0}
              expandedIds={expandedIds}
              selectedId={selectedId}
              onToggle={handleToggle}
              onSelect={onSelect}
            />
          ))}
        </ul>
      </div>
    );
  }
);

Tree.displayName = 'Tree';
