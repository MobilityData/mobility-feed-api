#!/usr/bin/env node
/**
 * GitHub Milestone Assignment Script
 * Assigns "next release" milestone to closed issues when merged to main
 * 
 * Usage:
 * 
 * 1. Setup Environment variables to run locally:
 *   export GITHUB_TOKEN="ghp_your_token_here"
 *   export GITHUB_REPOSITORY="MobilityData/mobility-feed-api"
 * 
 * 2. Install dependencies
 *   npm install @octokit/rest
 * 
 * 3. Run in dry mode
 *   node scripts/assign-next-release-milestone.js --dry-run
 * - Optional. If provided then the script will do a dry run without affecting any issues, logging will explain what will be done when running in production mode.
 * 
 * 4. Run in production mode
 *   node scripts/assign-next-release-milestone.js
 */

const { Octokit } = require('@octokit/rest');

// Parse command line arguments
const args = process.argv.slice(2);
const hasArgDryRun = args.includes('--dry-run');

// Determine dry run mode based on priority:
// 1. Command line argument --dry-run takes precedence
// 2. Environment variable DRY_RUN
// 3. Default to false
const isDryRun = hasArgDryRun || process.env.DRY_RUN === 'true';

// Validate required environment variables
const token = process.env.GITHUB_TOKEN;
const repository = process.env.GITHUB_REPOSITORY;

if (!token) {
  console.error('❌ GITHUB_TOKEN environment variable is required');
  process.exit(1);
}

if (!repository) {
  console.error('❌ GITHUB_REPOSITORY environment variable is required (format: owner/repo)');
  process.exit(1);
}

const [owner, repo] = repository.split('/');
if (!owner || !repo) {
  console.error('❌ GITHUB_REPOSITORY must be in format "owner/repo"');
  process.exit(1);
}

// Initialize Octokit
const octokit = new Octokit({
  auth: token,
});

async function main() {
  try {
    if (isDryRun) {
      console.log('RUNNING IN DRY RUN MODE - No changes will be made');
    }
    
    console.log(`Processing repository: ${owner}/${repo}`);

    // Get the "next release" milestone
    console.log('Fetching milestones...');
    const milestones = await octokit.rest.issues.listMilestones({
      owner,
      repo,
      state: 'open'
    });

    const nextReleaseMilestone = milestones.data.find(
      milestone => milestone.title.toLowerCase() === 'next release'
    );

    if (!nextReleaseMilestone) {
      console.log('❌ "Next Release" milestone not found');
      return;
    }

    console.log(`Found milestone: ${nextReleaseMilestone.title} (ID: ${nextReleaseMilestone.number})`);

    // Get all closed issues using search API, filtered to last 45 days
    console.log('Fetching closed issues...');
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - 45);
    const cutoffISO = cutoffDate.toISOString().split('T')[0];

    const query = `repo:${owner}/${repo} is:issue is:closed reason:completed closed:>=${cutoffISO}`;

    const issuesResponse = await octokit.rest.search.issuesAndPullRequests({
      q: query,
      per_page: 100,
      sort: 'updated',
      order: 'desc',
    });
    const issues = issuesResponse.data.items;

    console.log(`Found ${issues.length} closed issues`);

    let processedCount = 0;
    let assignedCount = 0;
    const assignedIssueNumbers = [];

    // Process each issue
    for (const issue of issues) {
      // Skip pull requests (they appear in issues API but have pull_request property)
      if (issue.pull_request) {
        continue;
      }

      processedCount++;

      // Skip if already has the next release milestone
      if (issue.milestone && issue.milestone.number === nextReleaseMilestone.number) {
        console.log(`Issue #${issue.number} already has Next Release milestone, skipping...`);
        continue;
      }

      // Check if issue was closed by a merged PR
      console.log(`Checking timeline for issue #${issue.number}...`);
      const timelineEvents = await octokit.rest.issues.listEventsForTimeline({
        owner,
        repo,
        issue_number: issue.number
      });

      // Debug log: print all timeline events for this issue
      console.log(`Timeline events for issue #${issue.number}:`);
      timelineEvents.data.forEach(event => {
        console.log(`- event: ${event.event}, actor: ${event.actor?.login || 'N/A'}, commit_id: ${event.commit_id || 'N/A'}, source type: ${event.source?.issue?.pull_request ? 'PR' : 'Other'}`);
      });

      const wasClosedByMergedPR = timelineEvents.data.some(event =>
        event.event === 'closed'
      );

      if (wasClosedByMergedPR) {
        console.log(`${isDryRun ? '[DRY RUN] Would assign' : 'Assigning'} milestone to issue #${issue.number}: ${issue.title}`);

        if (!isDryRun) {
          try {
            await octokit.rest.issues.update({
              owner,
              repo,
              issue_number: issue.number,
              milestone: nextReleaseMilestone.number
            });

            console.log(`✅ Successfully assigned milestone to issue #${issue.number}`);
            assignedCount++;
            assignedIssueNumbers.push(issue.number);
          } catch (error) {
            console.error(`❌ Failed to assign milestone to issue #${issue.number}:`, error.message);
          }
        } else {
          console.log(`[DRY RUN] Skipped actual assignment for issue #${issue.number}`);
          assignedCount++;
          assignedIssueNumbers.push(issue.number);
        }
      } else {
        console.log(`Issue #${issue.number} was not detected as closed, skipping`);
      }
    }

    console.log(`\n\nSummary:`);
    console.log(`- Processed ${processedCount} issues`);
    console.log(`- ${isDryRun ? 'Would assign' : 'Assigned'} milestone to ${assignedCount} issues`);
    console.log(`${isDryRun ? '[DRY RUN] Test complete!' : '✅ Milestone assignment complete!'}`);

    if (assignedIssueNumbers.length > 0) {
      console.log(`\nIssues ${isDryRun ? 'to be' : ''} assigned milestone: ${assignedIssueNumbers.join(', ')}`);
    }

  } catch (error) {
    console.error('❌ Script failed:', error.message);
    process.exit(1);
  }
}

// Run the script
main();