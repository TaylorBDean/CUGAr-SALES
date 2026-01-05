/**
 * Quick Actions Configuration for Sales Reps
 * Pre-configured prompts and workflows for common sales tasks
 */

export interface QuickAction {
  id: string;
  title: string;
  description: string;
  prompt: string;
  category: 'prospecting' | 'outreach' | 'qualification' | 'intelligence' | 'planning';
  icon: string;
  requiresContext?: string[]; // Required contextual data
  tools?: string[]; // Suggested tools to use
}

export const QUICK_ACTIONS: QuickAction[] = [
  // Territory & Planning
  {
    id: 'analyze-territory',
    title: 'Analyze My Territory',
    description: 'Get insights on coverage gaps and capacity',
    prompt: 'Analyze my sales territory for coverage gaps and capacity issues. Show me high-potential accounts I should focus on.',
    category: 'planning',
    icon: 'Map',
    tools: ['analyze_territory_coverage', 'identify_white_space']
  },
  {
    id: 'simulate-territory-change',
    title: 'Simulate Territory Change',
    description: 'Model impact of territory reassignment',
    prompt: 'Help me simulate adding {account_name} to my territory. What would the capacity impact be?',
    category: 'planning',
    icon: 'GitBranch',
    requiresContext: ['account_name'],
    tools: ['simulate_territory_change']
  },

  // Prospecting & Intelligence
  {
    id: 'score-prospect',
    title: 'Score Prospect Fit',
    description: 'Evaluate if prospect matches ICP',
    prompt: 'Score the account fit for {company_name}. Give me ICP match percentage and key signals.',
    category: 'intelligence',
    icon: 'Target',
    requiresContext: ['company_name'],
    tools: ['score_account_fit', 'normalize_company_data']
  },
  {
    id: 'research-account',
    title: 'Research Account',
    description: 'Deep dive on company background and signals',
    prompt: 'Research {company_name} comprehensively. I need: recent news, key executives, tech stack, buying signals, and competitive landscape.',
    category: 'intelligence',
    icon: 'Search',
    requiresContext: ['company_name'],
    tools: ['enrich_account_data', 'identify_buying_signals']
  },
  {
    id: 'find-decision-makers',
    title: 'Find Decision Makers',
    description: 'Identify key contacts at target account',
    prompt: 'Find the decision makers at {company_name} for {solution_type}. I need names, titles, and contact info.',
    category: 'intelligence',
    icon: 'Users',
    requiresContext: ['company_name', 'solution_type'],
    tools: ['identify_decision_makers']
  },

  // Outreach & Engagement
  {
    id: 'draft-cold-email',
    title: 'Draft Cold Email',
    description: 'Generate personalized outreach message',
    prompt: 'Draft a cold outreach email to {contact_name} at {company_name}. Focus on {pain_point}. Keep it under 150 words and include a clear CTA.',
    category: 'outreach',
    icon: 'Mail',
    requiresContext: ['contact_name', 'company_name', 'pain_point'],
    tools: ['draft_outbound_message', 'assess_message_quality']
  },
  {
    id: 'draft-follow-up',
    title: 'Draft Follow-Up',
    description: 'Create follow-up message for existing thread',
    prompt: 'Draft a follow-up message for {contact_name}. Last touchpoint was {days_ago} days ago. Reference: {previous_topic}',
    category: 'outreach',
    icon: 'Reply',
    requiresContext: ['contact_name', 'days_ago', 'previous_topic'],
    tools: ['draft_outbound_message', 'generate_sequence_steps']
  },
  {
    id: 'create-sequence',
    title: 'Build Email Sequence',
    description: 'Multi-touch campaign for prospect',
    prompt: 'Create a 5-touch email sequence for {persona} at {company_type} companies. Focus on {value_prop}. Space touches 3-4 days apart.',
    category: 'outreach',
    icon: 'ListOrdered',
    requiresContext: ['persona', 'company_type', 'value_prop'],
    tools: ['generate_sequence_steps', 'draft_outbound_message']
  },
  {
    id: 'use-template',
    title: 'Browse Templates',
    description: 'Access saved message templates',
    prompt: 'Show me available email templates for {use_case}',
    category: 'outreach',
    icon: 'FileText',
    requiresContext: ['use_case'],
    tools: ['manage_template_library']
  },

  // Qualification
  {
    id: 'qualify-opportunity',
    title: 'Qualify Opportunity',
    description: 'Run BANT/MEDDIC on active deal',
    prompt: 'Help me qualify the opportunity at {company_name}. I need BANT and MEDDIC scores with gaps identified.',
    category: 'qualification',
    icon: 'CheckSquare',
    requiresContext: ['company_name'],
    tools: ['qualify_opportunity', 'assess_deal_risk']
  },
  {
    id: 'assess-deal-risk',
    title: 'Assess Deal Risk',
    description: 'Identify blockers and risks',
    prompt: 'Analyze risk factors for the {company_name} deal. What could derail this and what should I mitigate?',
    category: 'qualification',
    icon: 'AlertTriangle',
    requiresContext: ['company_name'],
    tools: ['assess_deal_risk']
  },
  {
    id: 'next-best-action',
    title: 'What Should I Do Next?',
    description: 'Get recommended next steps for deal',
    prompt: 'What should my next action be for the {company_name} opportunity? Current stage: {deal_stage}',
    category: 'qualification',
    icon: 'Compass',
    requiresContext: ['company_name', 'deal_stage'],
    tools: ['recommend_next_action']
  },

  // Product Knowledge
  {
    id: 'explain-product-fit',
    title: 'Explain Product Fit',
    description: 'How our solution solves their problem',
    prompt: 'Explain how our {product_name} addresses {customer_pain_point} for {industry} companies.',
    category: 'intelligence',
    icon: 'Lightbulb',
    requiresContext: ['product_name', 'customer_pain_point', 'industry'],
    tools: ['retrieve_product_knowledge']
  },
  {
    id: 'compare-competitors',
    title: 'Competitive Battlecard',
    description: 'Compare us vs competitor',
    prompt: 'Give me a battlecard comparing our solution to {competitor_name}. Focus on {use_case}.',
    category: 'intelligence',
    icon: 'Swords',
    requiresContext: ['competitor_name', 'use_case'],
    tools: ['retrieve_product_knowledge', 'generate_battlecard']
  },

  // Smart Workflows
  {
    id: 'full-prospect-workflow',
    title: '🔥 Full Prospect Workflow',
    description: 'End-to-end: score → research → draft',
    prompt: 'I want to prospect {company_name}. Score their fit, research them deeply, identify the decision maker, and draft a personalized cold email.',
    category: 'prospecting',
    icon: 'Zap',
    requiresContext: ['company_name'],
    tools: [
      'score_account_fit',
      'enrich_account_data',
      'identify_decision_makers',
      'draft_outbound_message'
    ]
  }
];

// Category metadata
export const CATEGORIES = {
  prospecting: {
    label: 'Prospecting',
    color: '#0f62fe',
    icon: 'Target'
  },
  outreach: {
    label: 'Outreach',
    color: '#24a148',
    icon: 'Send'
  },
  qualification: {
    label: 'Qualification',
    color: '#8a3ffc',
    icon: 'CheckCircle'
  },
  intelligence: {
    label: 'Intelligence',
    color: '#ff832b',
    icon: 'Brain'
  },
  planning: {
    label: 'Planning',
    color: '#da1e28',
    icon: 'Map'
  }
};

/**
 * Get actions by category
 */
export function getActionsByCategory(category: string): QuickAction[] {
  return QUICK_ACTIONS.filter(action => action.category === category);
}

/**
 * Get action by ID
 */
export function getActionById(id: string): QuickAction | undefined {
  return QUICK_ACTIONS.find(action => action.id === id);
}

/**
 * Fill prompt template with context
 */
export function fillPromptTemplate(
  prompt: string,
  context: Record<string, string>
): string {
  let filled = prompt;
  Object.entries(context).forEach(([key, value]) => {
    filled = filled.replace(new RegExp(`\\{${key}\\}`, 'g'), value);
  });
  return filled;
}

/**
 * Validate required context
 */
export function validateContext(
  action: QuickAction,
  context: Record<string, string>
): { valid: boolean; missing: string[] } {
  if (!action.requiresContext) {
    return { valid: true, missing: [] };
  }

  const missing = action.requiresContext.filter(key => !context[key]);
  return {
    valid: missing.length === 0,
    missing
  };
}
