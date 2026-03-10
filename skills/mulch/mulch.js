/**
 * Mulch Code Mode Implementation
 * 
 * Only 2 tools: search() and execute()
 * Token-efficient memory system for agents
 * 
 * v2.1.0 - Smart Domain Inference
 * Automatically detects domain from content if not provided
 */

const fs = require('fs');
const path = require('path');

const MULCH_DIR = '.mulch';

/**
 * Smart Domain Inference
 * Automatically detects domain from content/path
 */
function inferDomain(content, explicitDomain, explicitPath) {
  // If domain explicitly provided, use it
  if (explicitDomain) return explicitDomain;
  
  const text = (content || '').toLowerCase();
  const fullText = text + ' ' + (explicitPath || '').toLowerCase();
  
  // Domain inference rules
  const rules = [
    { keywords: ['beautiful-mind', 'beautiful mind', 'skill'], domain: 'Skills' },
    { keywords: ['github', 'gh pr', 'gh issue', 'push', 'repo'], domain: 'GitHub' },
    { keywords: ['openclaw', 'claw'], domain: 'OpenClaw' },
    { keywords: ['telegram', 'tg ', 'telegram-glow'], domain: 'Telegram' },
    { keywords: ['sly', 'stealth'], domain: 'Sly' },
    { keywords: ['charlie', 'social media', 'tiktok', 'instagram'], domain: 'Social' },
    { keywords: ['memory', 'soul.md', 'history.md'], domain: 'Memory' },
    { keywords: ['config', 'yaml', 'settings'], domain: 'Config' },
    { keywords: ['cron', 'schedule', 'reminder'], domain: 'Automation' },
    { keywords: ['browser', 'chrome', 'playwright'], domain: 'Browser' },
    { keywords: ['npm install', 'pip install', 'dependencies', 'package'], domain: 'Dependencies' },
    { keywords: ['vision', 'image', 'ocr', 'llava'], domain: 'Vision' },
    { keywords: ['weather'], domain: 'Weather' },
    { keywords: ['humanizer', 'human'], domain: 'Humanizer' },
    { keywords: ['mulch', 'learning'], domain: 'Mulch' },
  ];
  
  for (const rule of rules) {
    for (const keyword of rule.keywords) {
      if (fullText.includes(keyword)) {
        return rule.domain;
      }
    }
  }
  
  return 'General';
}

/**
 * search - Filter memories using JavaScript code
 * @param {string} code - JS code to filter memories
 * @returns {Promise<Array>} Filtered learnings
 */
async function search(code) {
  try {
    // Parse the filter code
    const filterFn = new Function('mulch', code);
    
    // Load all domain files
    const learnings = [];
    
    if (!fs.existsSync(MULCH_DIR)) {
      return { status: 'no-mulch-dir', learnings: [] };
    }
    
    const files = fs.readdirSync(MULCH_DIR).filter(f => f.endsWith('.jsonl'));
    
    for (const file of files) {
      const domain = file.replace('.jsonl', '');
      const lines = fs.readFileSync(path.join(MULCH_DIR, file), 'utf-8').split('\n').filter(Boolean);
      
      for (const line of lines) {
        try {
          const record = JSON.parse(line);
          learnings.push({ ...record, domain });
        } catch (e) {
          // Skip malformed lines
        }
      }
    }
    
    // Apply filter
    const result = filterFn(learnings);
    
    return {
      status: 'success',
      count: result.length,
      results: result.slice(0, 10) // Limit to 10 for token efficiency
    };
    
  } catch (error) {
    return { status: 'error', message: error.message };
  }
}

/**
 * execute - Record or query learnings
 * @param {Object} params - Action parameters
 * @returns {Promise<Object>} Result
 */
async function execute(params) {
  const { action, domain, type, description, resolution, content, title, rationale, name, to, path: filePath } = params;
  
  // Smart domain inference
  const inferredDomain = inferDomain(content || description, domain, filePath);
  
  switch (action) {
    case 'record':
      return recordLearning({ 
        domain: inferredDomain, 
        type, 
        description, 
        resolution, 
        content, 
        title, 
        rationale, 
        name,
        autoInferred: domain ? false : true  // Track if auto-inferred
      });
    
    case 'query':
      return queryDomain(domain || inferredDomain);
    
    case 'promote':
      return promoteLearning(id, to);
    
    case 'search':
      // Alias for search()
      return search(code);
    
    case 'notify':
      // Send notification with smart domain
      return {
        status: 'notified',
        domain: inferredDomain,
        content: content || description,
        message: `🌱 Mulched to ${inferredDomain}: ${content || description}`
      };
    
    default:
      return { status: 'error', message: `Unknown action: ${action}` };
  }
}

/**
 * recordLearning - Save a new learning
 */
function recordLearning({ domain, type, description, resolution, content, title, rationale, name }) {
  const id = `${domain}:${Date.now()}`;
  const record = {
    id,
    type,
    timestamp: new Date().toISOString(),
    description,
    resolution,
    content,
    title,
    rationale,
    name
  };
  
  const filePath = path.join(MULCH_DIR, `${domain}.jsonl`);
  
  // Ensure directory exists
  if (!fs.existsSync(MULCH_DIR)) {
    fs.mkdirSync(MULCH_DIR, { recursive: true });
  }
  
  // Append to domain file
  fs.appendFileSync(filePath, JSON.stringify(record) + '\n');
  
  return { status: 'recorded', id, domain };
}

/**
 * queryDomain - Get all learnings for a domain
 */
function queryDomain(domain) {
  const filePath = path.join(MULCH_DIR, `${domain}.jsonl`);
  
  if (!fs.existsSync(filePath)) {
    return { status: 'no-domain', domain };
  }
  
  const lines = fs.readFileSync(filePath, 'utf-8').split('\n').filter(Boolean);
  const learnings = lines.map(line => JSON.parse(line));
  
  return { status: 'success', domain, count: learnings.length, learnings };
}

/**
 * promoteLearning - Move learning to project memory
 */
function promoteLearning(id, to) {
  // This would integrate with SOUL.md, AGENTS.md, etc.
  return { status: 'promoted', id, to };
}

module.exports = { search, execute };