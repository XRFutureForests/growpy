# Linear Workspace Guide - The Grove Repository

## Repository Role: Logic Tier - Tree Asset Generation Service

This repository is part of the **XR Future Forests Lab multi-repository architecture** and serves as the **Tree Asset Generation Service** within the Logic Tier. It coordinates with the central planning hub and other specialized repositories.

## Multi-Repository Architecture Context

### **Planning Hub**: XR Future Forests Lab Repository

- **Role**: Central planning and coordination workspace
- **Contains**: Architecture documentation, issue distribution, milestone tracking
- **Linear Integration**: Coordinates work across all three specialized repositories

### **This Repository**: The Grove (Tree Asset Generation)

- **Architecture**: Logic Tier - Tree Asset Generation Service
- **Linear Project**: Create Virtual Forest Ecosense (`50992750-6878-41ca-92a4-520f9ee40c0c`)
- **Team**: XR Future Forests (`5e3b87df-5f1a-4f70-8621-4ced0ed7bdcf`)
- **Focus**: 3D tree model generation for VR/AR applications using The Grove core

### **Sibling Repositories**

- **🗄️ Digital Twin Repository**: Data Tier implementation (PostgreSQL + PostGIS database)
- **☁️ Potree Docker Repository**: Logic Tier - Point Cloud Processing + Web Platform Service

## Project Structure

### Teams & Initiatives

- **Team: XR Future Forests** - VR/AR forest visualization projects
  - **Initiative: XRFF FoWiTA** - Main research initiative
- **Team: 3Dtrees** - Point cloud processing and web visualization
  - **Initiative: MVP for SilviLaser Demo** - Conference demo preparation

### Workspace-per-Project Approach

Each Linear project gets its own dedicated workspace:

- Focused development environment
- Project-specific dependencies and configurations
- Clear separation of concerns
- Easier context switching between projects

## Linear Integration via MCP

### Available MCP Functions

The workspace has Linear MCP integration enabling:

- `mcp_linear_list_my_issues` - Get my assigned issues
- `mcp_linear_list_issues` - List issues (with filters)
- `mcp_linear_list_projects` - Get project information
- `mcp_linear_list_teams` - Team details
- `mcp_linear_create_issue` - Create new issues
- `mcp_linear_update_issue` - Update existing issues
- `mcp_linear_get_issue` - Get specific issue details
- And more...

### Authentication

Linear MCP is configured and authenticated. Access tokens are managed through MCP configuration.

## Current Workspace Context

### Project: Create Virtual Forest Ecosense

- **Team**: XR Future Forests (XRF)
- **Project ID**: `50992750-6878-41ca-92a4-520f9ee40c0c`
- **Timeline**: July 18 - September 19, 2025
- **Lead**: Paul Lakos
- **My Role**: Tree generation using The Grove core

### My Contribution

Generating realistic, procedurally generated trees that match real Ecosense forest data:

- **Input**: Tree positions, species, heights from digital twin database
- **Process**: Use The Grove to generate matching trees
- **Output**: USD tree models for VR integration
- **Key Technologies**: The Grove 22, Python, USD, scikit-learn

### Current Issues Status

- **Completed**: Core pipeline, species mapping, LOD generation, twig integration
- **In Progress**: Twig orientation fixes (HIGH priority)
- **Planned**: Database API integration, growth model improvements

## Workflow for AI Assistants

### When Starting Work in This Workspace

1. **Get Project Context**

   ```
   Use mcp_linear_get_project with project name or ID
   ```

2. **Check My Current Issues**

   ```
   Use mcp_linear_list_my_issues to see assigned work
   ```

3. **Understand Issue Status**

   ```
   Use mcp_linear_list_issues with projectId filter
   ```

4. **Analyze Workspace**
   - Read key files to understand current implementation
   - Check git status for recent changes
   - Review documentation and README files

### When Creating Issues

1. **Use Interview Approach**
   - Ask about current work status
   - Identify completed vs. outstanding tasks
   - Understand priorities and dependencies

2. **Create Comprehensive Issues**
   - Include clear acceptance criteria
   - Mark completed work with ✅ checkboxes
   - Set appropriate priorities and due dates
   - Link to relevant team and project

3. **Assessment Questions**
   - What's working vs. what needs work?
   - What are the main technical challenges?
   - Timeline and priority considerations?
   - Dependencies on other team members?

### Standard Issue Types to Create

1. **Completed Work Issues** (for project overview)
   - Mark with ✅ in acceptance criteria
   - Show substantial progress made
   - Can be immediately marked as "Done"

2. **Current Challenges** (high priority)
   - Technical blockers
   - Integration issues
   - Performance problems

3. **Future Work** (medium/low priority)
   - API integrations
   - Optimizations
   - Feature enhancements

## Template Workflow

### Initial Workspace Assessment

```markdown
# Project Context: Create Virtual Forest Ecosense

## Essential Project Information
- **Project ID**: `50992750-6878-41ca-92a4-520f9ee40c0c`
- **Team**: XR Future Forests (`5e3b87df-5f1a-4f70-8621-4ced0ed7bdcf`)
- **Timeline**: July 18 - September 19, 2025
- **Lead**: Paul Lakos
- **My Role**: Tree generation using The Grove

## My Specific Contribution
Generate USD tree models matching Ecosense forest digital twin data:
- **Input**: CSV with tree positions, species, heights
- **Process**: Grove tree generation with growth cycle calculations
- **Output**: Multi-LOD USD files with point-instanced twigs
- **Integration**: Delivers to Paul's VR forest system

## Current Technical Status
- ✅ **Working**: Core pipeline, species mapping, LOD generation, basic twig integration
- 🔧 **Priority**: Twig orientation fixes (due Aug 15)
- 📋 **Planned**: Database API integration, growth model improvements

## Key Project Files
- `debug_grove_core.py` - Main testing script
- `data/tree_asset_lookup.csv` - Species mapping
- `data/input/small_demo.csv` - Test data format
- `src/growpy/` - Grove integration modules

## Main Technical Challenge
**Twig Orientation**: Point-instanced twigs not facing correct direction in USD export

---
*General workflow: `.github/instructions/linear.instructions.md`*
```

### Issue Creation Pattern

```markdown
## For Each Major Component:

1. **Setup/Infrastructure Issues** (usually completed)
2. **Core Implementation Issues** (mix of done/in-progress)
3. **Integration Issues** (often in-progress)
4. **Optimization Issues** (usually future work)
5. **Documentation Issues** (often future work)
```

## Key Commands Reference

### Essential Linear MCP Commands

```bash
# Get my work
mcp_linear_list_my_issues

# Get project details
mcp_linear_get_project "project-name"

# List project issues
mcp_linear_list_issues projectId="PROJECT_ID"

# Create new issue
mcp_linear_create_issue assigneeId="USER_ID" title="..." description="..." projectId="PROJECT_ID" teamId="TEAM_ID"

# Update issue status
mcp_linear_update_issue id="ISSUE_ID" stateId="STATE_ID"
```

### My User ID

`5b1ad7e6-6e86-4f20-ba34-d2d70c93eab3`

### Team IDs

- **XR Future Forests**: `5e3b87df-5f1a-4f70-8621-4ced0ed7bdcf`
- **3Dtrees**: `7ac53333-6ade-4845-b5f5-76ead398222d`

## Notes for Future Workspaces

1. **Copy this file** to each new project workspace
2. **Update project-specific sections** (project name, ID, timeline, role)
3. **Maintain consistency** in issue creation approach
4. **Document workspace-specific context** (technologies, dependencies, etc.)

## Benefits of This Approach

- **Consistent project management** across all workspaces
- **Rapid AI assistant onboarding** in any workspace
- **Clear progress tracking** with completed/pending issues
- **Better project visibility** for stakeholders
- **Simplified context switching** between projects

---

*Last Updated: July 30, 2025*
*Workspace: the-grove (Ecosense Virtual Forest)*
