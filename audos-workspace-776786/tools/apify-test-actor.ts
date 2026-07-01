/**
 * Apify Actor Test Tool
 * 
 * Tests an Apify actor by running it with minimal input to understand
 * its input/output structure. Uses LLM to generate test input and
 * analyze the results.
 * 
 * Required Environment Variables:
 *   - APIFY_API_TOKEN: Your Apify API token
 *   - OPENAI_API_KEY: Your OpenAI API key
 * 
 * Usage:
 *   ts-node tools/apify-test-actor.ts <actorId> [actorName] [actorDescription]
 * 
 * Examples:
 *   ts-node tools/apify-test-actor.ts "apify/instagram-scraper"
 *   ts-node tools/apify-test-actor.ts "apify/web-scraper" "Web Scraper" "Scrapes any website"
 */

import OpenAI from 'openai';

async function generateTestInput(actorId: string, actorName: string, actorDescription?: string): Promise<any> {
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  
  const prompt = `You are helping generate minimal test input for an Apify web scraping actor.

Actor: ${actorName}
Actor ID: ${actorId}
Description: ${actorDescription || 'No description available'}

Generate the MINIMAL input JSON needed to run a quick test of this actor. The input should:
- Request just 1-3 items to keep the test fast and cheap
- Use publicly accessible data (no authentication required if possible)
- Be realistic but minimal

Common patterns:
- Instagram scraper: { "username": ["nike"], "resultsLimit": 3 }
- LinkedIn scraper: { "startUrls": ["https://linkedin.com/in/williamhgates"], "maxResults": 3 }
- Google search: { "queries": ["test query"], "maxPagesPerQuery": 1, "resultsPerPage": 3 }
- Amazon scraper: { "searchTerms": ["laptop"], "maxResults": 3 }
- Twitter scraper: { "searchTerms": ["#technology"], "maxTweets": 3 }

Return ONLY the JSON object, no explanations:`;

  console.log('🤖 Generating test input with LLM...');

  const response = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 500,
    temperature: 0.3
  });
  
  const content = response.choices[0]?.message?.content || '{}';
  
  const jsonMatch = content.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/) || content.match(/(\{[\s\S]*\})/);
  const jsonStr = jsonMatch ? jsonMatch[1] : content;
  
  return JSON.parse(jsonStr);
}

async function analyzeOutput(
  actorId: string,
  actorName: string,
  sampleInput: any,
  sampleOutput: any[]
): Promise<{ inputSchema: string; outputSchema: string; code: string }> {
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  
  const prompt = `You are a TypeScript expert helping analyze an Apify actor's input/output structure.

Actor: ${actorName}
Actor ID: ${actorId}

Sample Input:
\`\`\`json
${JSON.stringify(sampleInput, null, 2)}
\`\`\`

Sample Output (first 3 items):
\`\`\`json
${JSON.stringify(sampleOutput.slice(0, 3), null, 2)}
\`\`\`

Analyze this actor and provide:
1. A clear description of the input structure and key fields
2. A clear description of the output structure and available fields
3. Complete TypeScript code showing how to use this actor in a workspace app

The code should:
- Include TypeScript interfaces for input and output
- Show the fetch call to /api/apify-actor
- Include proper error handling
- Show how to access key fields in the response
- Be ready to copy-paste into a React component

Format your response as:
INPUT_SCHEMA: [description]
OUTPUT_SCHEMA: [description]
CODE:
\`\`\`typescript
[code here]
\`\`\``;

  console.log('🤖 Analyzing output with LLM...');

  const response = await openai.chat.completions.create({
    model: 'gpt-4o',
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 2000,
    temperature: 0.2
  });
  
  const content = response.choices[0]?.message?.content || '';
  
  const inputSchemaMatch = content.match(/INPUT_SCHEMA:\s*([\s\S]+?)(?=OUTPUT_SCHEMA:|CODE:|$)/);
  const outputSchemaMatch = content.match(/OUTPUT_SCHEMA:\s*([\s\S]+?)(?=CODE:|$)/);
  const codeMatch = content.match(/CODE:\s*```(?:typescript|ts)?\s*([\s\S]+?)```/);
  
  return {
    inputSchema: inputSchemaMatch?.[1].trim() || 'Input structure not documented',
    outputSchema: outputSchemaMatch?.[1].trim() || 'Output structure not documented',
    code: codeMatch?.[1].trim() || content
  };
}

async function main() {
  const args = process.argv.slice(2);
  const actorId = args[0];
  const actorName = args[1] || actorId;
  const actorDescription = args[2];

  if (!actorId) {
    console.error('Error: Actor ID is required');
    console.error('Usage: ts-node tools/apify-test-actor.ts <actorId> [actorName] [actorDescription]');
    process.exit(1);
  }

  if (!process.env.APIFY_API_TOKEN) {
    console.error('Error: APIFY_API_TOKEN environment variable is required');
    process.exit(1);
  }

  if (!process.env.OPENAI_API_KEY) {
    console.error('Error: OPENAI_API_KEY environment variable is required');
    process.exit(1);
  }

  console.log(`\n🔬 Testing Apify Actor: ${actorName}`);
  console.log(`📋 Actor ID: ${actorId}\n`);

  try {
    // Step 1: Generate test input
    const testInput = await generateTestInput(actorId, actorName, actorDescription);
    console.log('✅ Generated test input');
    console.log(`📥 Input:`, JSON.stringify(testInput, null, 2));
    console.log();

    // Step 2: Create apifyService instance and run the actor
    // (Use factory function to avoid constructor validation before our env checks)
    console.log(`🚀 Starting actor run: ${actorId}`);
    console.log(`⏱️  Timeout: 2 minutes`);
    console.log(`💾 Memory: 512 MB`);
    console.log(`⏳ Waiting for completion...\n`);
    
    const { createApifyService } = await import('../server/services/apify-service.js');
    const apifyService = createApifyService(process.env.APIFY_API_TOKEN!);
    
    const result = await apifyService.runActor({
      actorId,
      input: testInput,
      timeout: 2,
      memory: 512
    });

    if (result.status !== 'succeeded' || !result.results || result.results.length === 0) {
      throw new Error(`Test run failed: ${result.metadata.errorMessage || 'No results returned'}`);
    }

    console.log(`✅ Run completed successfully`);
    console.log(`📊 Items scraped: ${result.results.length}`);
    console.log();

    // Step 3: Analyze the output
    const analysis = await analyzeOutput(actorId, actorName, testInput, result.results);
    
    console.log('\n📊 Analysis Complete\n');
    console.log('=== INPUT STRUCTURE ===');
    console.log(analysis.inputSchema);
    console.log('\n=== OUTPUT STRUCTURE ===');
    console.log(analysis.outputSchema);
    console.log('\n=== USAGE CODE ===');
    console.log(analysis.code);
    console.log('\n=== SAMPLE DATA ===');
    console.log(JSON.stringify(result.results.slice(0, 3), null, 2));

    // Output structured JSON for programmatic use
    console.log('\n\n--- JSON Output ---');
    console.log(JSON.stringify({
      actorId,
      actorName,
      testInput,
      sampleOutput: result.results.slice(0, 3),
      analysis: {
        inputSchema: analysis.inputSchema,
        outputSchema: analysis.outputSchema,
        code: analysis.code
      },
      metadata: {
        itemCount: result.results.length,
        status: result.status
      }
    }, null, 2));

  } catch (error) {
    console.error('\n❌ Test failed:', error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main();
