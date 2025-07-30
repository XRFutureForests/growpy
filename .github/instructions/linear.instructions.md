````instructions
---
applyTo: '**'
---

# Linear + MCP Project Management Instructions

## Overview
This user follows a structured project management approach using Linear issues, MCP (Model Context Protocol) integration, and dedicated VS Code workspaces per project. These instructions help AI assistants quickly understand and work within this system.

## Critical AI Assistant Directives

### ALWAYS DO FIRST
1. **Use Linear MCP** to check project context when user asks about work
2. **Check for LINEAR_WORKSPACE_GUIDE.md** for project-specific details
3. **Interview the user** before creating issues (see workflow below)
4. **Create completed work issues** to show progress, not just outstanding tasks

### NEVER DO
- Create issues without understanding current project state
- Make assumptions about user's role or progress
- Skip the interview process for issue creation
- Create vague or unmeasurable acceptance criteria

## Project Structure

### Teams & Initiatives
- **Team: XR Future Forests** (teamId: `5e3b87df-5f1a-4f70-8621-4ced0ed7bdcf`)
  - Initiative: XRFF FoWiTA - VR/AR forest visualization projects
- **Team: 3Dtrees** (teamId: `7ac53333-6ade-4845-b5f5-76ead398222d`)
  - Initiative: MVP for SilviLaser Demo - Point cloud processing and web visualization

### User Information
- **User ID**: `5b1ad7e6-6e86-4f20-ba34-d2d70c93eab3`
- **Email**: maximilian.sperlich@gmail.com

## Linear MCP Integration

### When to Use Linear MCP
ALWAYS use Linear MCP functions when:
- User asks about current work, issues, or project status
- User wants to create, update, or manage issues
- Starting work in a new workspace (to understand project context)
- User asks about team members, projects, or timelines

### Essential MCP Commands (USE THESE FREQUENTLY)
```bash
# STEP 1: Always start with these
mcp_linear_list_my_issues                    # Get user's assigned work
mcp_linear_get_project "project-name"        # Understand current project

# STEP 2: Detailed investigation  
mcp_linear_list_issues projectId="PROJECT_ID"  # Get all project issues
mcp_linear_get_issue id="ISSUE_ID"             # Get specific issue details

# STEP 3: Issue management
mcp_linear_create_issue                      # Create new issues
mcp_linear_update_issue                      # Update existing issues
mcp_linear_list_teams                        # Get team information
mcp_linear_list_projects                     # Browse available projects
```

### Required Parameters for Issue Creation
- **assigneeId**: `5b1ad7e6-6e86-4f20-ba34-d2d70c93eab3` (user's ID)
- **teamId**: Use appropriate team ID from below
- **projectId**: Get from mcp_linear_get_project
- **priority**: 1=Urgent, 2=High, 3=Medium, 4=Low
- **title**: Verb-based, specific action
- **description**: Use template structure below

## Workspace-per-Project Approach

### Philosophy
Each Linear project gets its own dedicated VS Code workspace:
- Focused development environment per project
- Project-specific dependencies and configurations
- Clear separation of concerns between projects
- Easier context switching

### When Starting in Any Workspace
1. **Check for LINEAR_WORKSPACE_GUIDE.md** - Contains project-specific context
2. **Use `mcp_linear_get_project`** to understand the current project
3. **Use `mcp_linear_list_my_issues`** to see assigned work
4. **Analyze workspace files** to understand current implementation state

## AI Assistant Workflow

### MANDATORY: Initial Assessment Process
When user asks about their work or wants to create issues, follow this interview approach:

**Interview Questions (Ask ALL of these):**

1. **Role Identification**
   - "What is your main responsibility in this [PROJECT] project?"
   - "What's your specific contribution vs. team members?"

2. **Current Status Assessment** 
   - "What's currently working vs. what needs attention?"
   - "What are your main technical challenges?"
   - "What have you already implemented or completed?"

3. **Priority Understanding**
   - "What should be prioritized for the project timeline?"
   - "What are the key deadlines or milestones?"

4. **Dependency Mapping**
   - "What do you need from other team members?"
   - "Are there external system dependencies?"

### Issue Creation Strategy (CRITICAL)

#### Create BOTH Types of Issues:

1. **Completed Work Issues** (HIGH IMPORTANCE)
   - Purpose: Show project progress and value delivered
   - Mark acceptance criteria with ✅ 
   - Can be immediately marked as "Done"
   - Help demonstrate substantial progress made
   - **Create 4-6 of these to show user's accomplishments**

2. **Outstanding Work Issues** (for task management)
   - Clear acceptance criteria with [ ] checkboxes
   - Appropriate priority levels (1=Urgent, 2=High, 3=Medium, 4=Low)
   - Realistic due dates based on project timelines
   - Dependencies and technical context

#### MANDATORY Issue Template Structure:
```markdown
## Objective/Problem
[Clear statement of what needs to be accomplished]

## Current Status
- ✅ What's already working
- ❌ What needs to be fixed/implemented

## Acceptance Criteria
- [ ] Specific, measurable outcomes
- [ ] Technical requirements  
- [ ] Quality/performance criteria

## Technical Context
- Technologies involved
- Integration points
- Performance considerations

## Dependencies
- Other team members' work
- External systems
- Timeline constraints
```

## Example: Successful Issue Creation Session

### Based on Real Example: "The Grove" Tree Generation Project

**Context Discovery:**
- User's role: Tree generation using The Grove for VR forest
- Current status: Core pipeline working, twig orientation needs fixing
- Priority: Twig orientation (High), Growth models (Low)

**Issues Created:**
1. **Completed Work Issues** (5 issues marked as Done):
   - Setup Grove core integration ✅
   - Create species mapping table ✅  
   - Implement growth cycle calculation ✅
   - Multi-LOD tree generation ✅
   - Basic twig integration ✅

2. **Outstanding Work Issues** (3 active tasks):
   - Fix twig orientation (High priority, due Aug 15)
   - Database API integration (Medium priority)
   - Improve growth models (Low priority)

**Result:** Clear project overview showing 75% completion with specific next steps.

## Code and Technical Guidance

### When Writing Code:
- Follow the user's established patterns and architecture
- Consider the project's technical stack and constraints
- Prioritize VR/performance considerations for XR projects
- Maintain compatibility with existing integrations

### When Analyzing Workspaces:
- Look for key files: README, package.json, requirements.txt, environment.yml
- Check `LINEAR_WORKSPACE_GUIDE.md` for project context
- Understand the project's build and deployment setup
- Identify main technologies and frameworks in use
- Check for existing documentation and coding standards

## Linear Issue Management Best Practices

### Priority Levels:
- **Urgent (1)**: Project blockers, critical bugs
- **High (2)**: Core functionality, near-term deadlines
- **Medium (3)**: Important features, future milestones  
- **Low (4)**: Optimizations, nice-to-have features

### Due Dates:
- Align with project timelines (check project targetDate)
- Consider dependencies between issues
- Leave buffer time for integration and testing

### Descriptions:
- Include technical context for implementation
- Reference specific files, functions, or systems
- Document current state and desired outcome
- Add acceptance criteria that can be verified

## Project-Specific Considerations

### XR Future Forests Projects:
- VR performance is critical (frame rate, LOD systems)
- Unity integration requirements
- Real-world data accuracy (digital twin fidelity)
- User experience in VR environments

### 3Dtrees Projects:
- Web-based visualization performance
- Point cloud processing efficiency
- API design for external integrations
- Scalability for large datasets

## Communication Style

### With User:
- Be direct and action-oriented
- Focus on practical next steps
- Acknowledge completed work before discussing remaining tasks
- Ask clarifying questions to understand priorities

### In Linear Issues:
- Use clear, professional language
- Include technical details for implementation
- Structure information with markdown formatting
- Cross-reference related issues when relevant

## Success Metrics

### Good AI Assistant Behavior:
- Quickly understands project context using Linear MCP
- Creates comprehensive, actionable issues (4-6 completed + 2-4 outstanding)
- Recognizes and celebrates completed work before discussing remaining tasks
- Provides realistic timelines and priorities
- Maintains consistency across workspaces
- Uses interview approach to understand user's actual situation

### Avoid:
- Making assumptions about project state without checking Linear
- Creating vague or unmeasurable issues
- Ignoring existing team structure and responsibilities
- Overlooking technical constraints or dependencies
- Creating only future work without showing completed progress

## Quick Reference

### User Information
- **User ID**: `5b1ad7e6-6e86-4f20-ba34-d2d70c93eab3`
- **Email**: maximilian.sperlich@gmail.com

### Team IDs
- **XR Future Forests**: `5e3b87df-5f1a-4f70-8621-4ced0ed7bdcf`
- **3Dtrees**: `7ac53333-6ade-4845-b5f5-76ead398222d`

### Essential File to Check
- `LINEAR_WORKSPACE_GUIDE.md` (contains project-specific context)

---

*These instructions apply to all workspaces and should be used consistently for project management tasks.*