/**
 * Human-readable names for agent tools
 */

const TOOL_NAME_PREFIX_RE = /^(?:functions\.|tools\.)/;

const toolNameAliases: Record<string, string> = {
  'edit_file': 'edit',
  'read_file': 'read',
  'list_files': 'ls',
  'run_command': 'bash',
  'shell': 'bash',
};

const toolTerms: Record<string, string> = {
  // File operations
  'read': 'reading file',
  'write': 'writing file',
  'edit': 'editing file',
  'glob': 'finding files',
  'grep': 'searching code',
  'ls': 'listing files',

  // Search operations
  'search_codebase': 'searching codebase',
  'do_web_search': 'searching the web',
  'web_fetch': 'fetching webpage',

  // Code operations
  'bash': 'running command',
  'get_server_logs': 'checking logs',

  // Generation
  'generate_image_tool': 'generating image',
  'generate_video_tool': 'generating video',

  // Default actions
  'thinking': 'thinking',
};

const toolColors: Record<string, string> = {
  // File operations - blue
  'read': 'text-blue-600',
  'write': 'text-green-600',
  'edit': 'text-amber-600',
  'glob': 'text-blue-500',
  'grep': 'text-indigo-600',
  'ls': 'text-blue-400',

  // Search - sky/blue (brand-aligned)
  'search_codebase': 'text-sky-600',
  'do_web_search': 'text-sky-500',
  'web_fetch': 'text-sky-400',

  // Code - gray
  'bash': 'text-gray-600',
  'get_server_logs': 'text-gray-500',

  // Generation - pink
  'generate_image_tool': 'text-pink-600',
  'generate_video_tool': 'text-pink-500',

  // Default
  'thinking': 'text-gray-500',
};

export function normalizeToolName(toolName?: string | null): string {
  if (!toolName) {
    return '';
  }

  const strippedName = String(toolName).trim().replace(TOOL_NAME_PREFIX_RE, '');
  return toolNameAliases[strippedName] || strippedName;
}

export function getFriendlyTerm(toolName: string, fallback?: string): string {
  const normalizedToolName = normalizeToolName(toolName);
  return toolTerms[normalizedToolName] || fallback || normalizedToolName || toolName;
}

export function getToolColor(toolName: string): string {
  return toolColors[normalizeToolName(toolName)] || 'text-gray-500';
}
