/**
 * Apify Actor Search Tool
 * 
 * Searches the Apify Store for actors matching a query.
 * Returns relevant actors with stats, pricing, and descriptions.
 * 
 * Usage:
 *   ts-node tools/apify-search-actors.ts <query> [limit]
 * 
 * Examples:
 *   ts-node tools/apify-search-actors.ts "instagram scraper"
 *   ts-node tools/apify-search-actors.ts "linkedin" 10
 * 
 * Note: No API key required - searches public Apify Store
 */

import fetch from 'node-fetch';

interface ActorSearchResult {
  id: string;
  name: string;
  description: string;
  username: string;
  actorId: string;
  stats: {
    runs: number;
    users: number;
  };
  categories: string[];
  pricing: string;
}

async function searchActors(query: string, limit: number = 10): Promise<ActorSearchResult[]> {
  const searchLimit = Math.min(limit, 100);
  
  const response = await fetch(
    `https://api.apify.com/v2/store?search=${encodeURIComponent(query)}&limit=${searchLimit}`
  );

  if (!response.ok) {
    throw new Error(`Apify Store API error: ${response.statusText}`);
  }

  const data = await response.json() as any;
  
  const actors = (data.data?.items || []).map((actor: any) => ({
    id: actor.id,
    name: actor.title || actor.name,
    description: actor.description,
    username: actor.username,
    actorId: `${actor.username}/${actor.name}`,
    stats: {
      runs: actor.stats?.totalRuns || 0,
      users: actor.stats?.totalUsers || 0
    },
    categories: actor.categories || [],
    pricing: actor.pricingModel || (actor.isFree ? 'FREE' : 'PAID')
  }));

  return actors;
}

async function main() {
  const args = process.argv.slice(2);
  const query = args[0];
  const limit = parseInt(args[1] || '10');

  if (!query) {
    console.error('Error: Search query is required');
    console.error('Usage: ts-node tools/apify-search-actors.ts <query> [limit]');
    process.exit(1);
  }

  console.log(`🔍 Searching Apify Store for: "${query}"...\n`);

  try {
    const actors = await searchActors(query, limit);
    
    if (actors.length === 0) {
      console.log('No actors found matching your query.');
      return;
    }

    console.log(`Found ${actors.length} actor(s):\n`);
    
    actors.forEach((actor, index) => {
      console.log(`${index + 1}. ${actor.name}`);
      console.log(`   Actor ID: ${actor.actorId}`);
      console.log(`   Description: ${actor.description.slice(0, 100)}${actor.description.length > 100 ? '...' : ''}`);
      console.log(`   Stats: ${actor.stats.users.toLocaleString()} users, ${actor.stats.runs.toLocaleString()} runs`);
      console.log(`   Pricing: ${actor.pricing}`);
      console.log(`   Categories: ${actor.categories.join(', ')}`);
      console.log();
    });

    // Output JSON for programmatic use
    console.log('\n--- JSON Output ---');
    console.log(JSON.stringify(actors, null, 2));
    
  } catch (error) {
    console.error('Search failed:', error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main();
