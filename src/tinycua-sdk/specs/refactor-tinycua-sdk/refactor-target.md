# Refactor Plan
In this document is written findings that needs clarification and codebases that needs to be refactored.
It will be written in their own section on what is unclear that needs clarification or design that needs to be cleaned up or refactored.

Legends for ID:
H - High Priority
M - Medium Priority
L - Low Priority

---

## Session
### File Location : 
- src/tinycua-sdk/tinycua_sdk/session/session.py 
- src/tinycua-sdk/tinycua_sdk/utils/session.py
### Questions : 
1. Is session not stored in database? SQLite or PostgreSQL? 
2. Based on src/tinycua-sdk/tinycua_sdk/storage/models.py this seems to conflict with the session.py system. 
3. Session system in this file seems to conflict with implementation on /media/christopher-sebastian/Sad-Drive/Backups/Code/Skripsi/TINYCUA/.worktrees/refactor-tinycua-sdk/src/tinycua-sdk/tinycua_sdk/storage/store.py

### Issue :
1. [H-01] - The file mentioned seem to be old implementation that should have been removed.

### Recommendation : 
1. [H-01] - Verify if session in src/tinycua-sdk/tinycua_sdk/session/session.py and src/tinycua-sdk/tinycua_sdk/utils/session.py are still used. If not we should remove this because we have the correct session approach of storing in DB, local using SQLite with ability to connect to PostgreSQL.

---

## Storage
File Location :
- src/tinycua-sdk/tinycua_sdk/storage

### Questions :
-

### Issue :
1. [H-02] - Right now modules are named as such :
snapshot.py --> Memory
store.py --> Session
export.py --> Exporter
importer.py --> Importer

2. [H-03] - Right now connection to SQLite is handled by sqlite.py while remote remains "unclear"
3. [H-04] - snapshot.py memory management seem to not really take advantage of using database to store memory. Memory should be stored inside a database and is Session Scoped.
### Recommendation :
1. [H-02] - Refactor Storage folder content as it is too high-level.
What should be done instead is these modules should no longer exists in storage/
instead their own module folder
snapshot.py --> memory/memory.py
importer.py and export.py --> data/importer.py and data/export.py
store.py --> session/store.py

as for model definition it should exist within their own folder
for example models related to session should exist in session/

as for sqlite.py it will be addressed in the upcoming recommendation.
2. [H-03] - Generalize and abstract database backend handling.
We should have a StorageBackend base class which can be extended to Local and Remote, both will have the same function name but different functionality based on if they are Local or Remote. Local connect to SQLite and Remote connect to a PostgreSQL URL.
All data that is stored in the database should have this StorageBackend as their attribute.
This class should also be extendable should there be a module that requires their own StorageBackend. But it will still have to use this as their Base Class.
For SQLite storage tables creation it should follow the existing models of module that can be stored so it remain to have same parity and compatible with the PostgreSQL seemlessly.
Should the storage be complex and can't be done with just using SQLite for example vectorDB, we should have the option to extend the StorageBackend for that said module to use their proper storage that can be synced with the PostgreSQL database.

The file should remain at storage/ folder
storage/backend.py
storage/local.py
storage/remote.py

for the remote storage or the backend connected storage it should expect to access API endpoint and is just purely sending the data through an endpoint.
This way we can just adjust backend to have that endpoint and then let how the data is stored handled by the backend.

Consideration:
Instead of having storage/local.py and storage/remote.py
every module that requires storage will have backend.py to define how they each handle their local and remote backend instead

The general rule will be all will use the interface and function defined by StorageBackend. If there are new function introduced by the backend it should all remain as internal function with __ prefix.

Pros : High flexibility as not all storage might use Databases
Cons : Can increase Code Complexity

Human Recommendation : I think its better to let each module handle their own storage backend classes (Will be related with future issue and recommendations)


3. [H-04] - Refactor Memory System
Previously we wanted to have Long-term and short-term memory.
But now we should generalize, Memory is always a "Long-term" memory that is stored across sessions and is persistent until deleted.

---

## Tools
### File Location :
- src/tinycua-sdk/tinycua_sdk/tools

### Questions :
-

### Issues :
1. [H-05] - Tool does not seem to have the same consistencies of being able to be stored in a database
2. [H-06] - Memory Tools does not seem to have correlation with memory snapshot system
3. [M-01] - Tool module are messy structure wise
### Recommendation :
1. [H-05] - We should also have a Tool model with ToolStorageBackend that handles remote and local storage.
This backend is going to be slightly more complex than previous storage as it should consider
ToolMetadata and ToolSource
ToolMetadata --> Metadata of the tools
ToolSource --> The file path or location of where the tool source code is stored. This could include using MinIO

Consideration:
Tool might need dependency resolver
Human Recommendation : For tool depedency resolver we should probably defer to future PR but we need to make the design ready for this
Current design idea : Every tool should include their "additional" dependencies to install. Everytime tool is stored it will also create it's own .venv to run the tool. Everytime tool is run it will use the .venv that the tool has.

2. [H-06] - Update memory tools to use actual memory system that is not defined by the tools but defined by the memory modules instead of the memory.py inside tools
3. [M-01] - Restructure the Tool module structure. We should not define tool in tools/ directly.
tools/ should remain to be "SDK" modules for example BaseTool.py decorators.py etc
Instead if we have a tool that will be owned by all agents it should be defined in tools/native/ for example memory_tools

## Skills
### File Location :
- src/tinycua-sdk/tinycua_sdk/skills

### Question :
-

### Issues :
1. [M-02] - Skills backend is its own "Backend" base
2. [H-07] - at tools.py Skill seem to have it's own tool system.
3. [L-01] - Based on Skill model we have path. It is unclear if it only support local dir or if it can support remote like MinIO
### Recommendation :
1. [M-02] - Skill backend should be based on StorageBackend to determine whether it is remote or local. 
2. [H-07] - Tools that skill use should be the same as the tool system we already have.
Tools that are used by the Agent to learn skill etc should be in tools/native instead of the skill directory.
Consideration :
CallableTool seem to be wrapper for "Skills" Tool it does not seem to be necessary because couldn't we just use the tool class directly. But if this is necessary then this issue can be invalidated. If this issue is ever invalidated give a reason why.
3. [L-01] - Ensure that skill can work using local dir and MinIO to remain consistent with Tool storage path.

## CLI
### File Location :
- src/tinycua-sdk/tinycua_sdk/cli

### Question :
-

### Issues :
1. [H-08] - CLI should no longer be part of the SDK

### Recommendation :
1. [H-08] - Remove CLI from the SDK

## Core
### File Location :
- src/tinycua-sdk/tinycua_sdk/core

### Question :
- 
### Issue :
1. [L-02] - There is still mention of lmstudio as Provider and base url "http://localhost:1234"
2. [H-09] - ToolRegistry is defined in core.py
3. [L-03] - Config have environment "dev"
4. [M-03] - Some Modules seems to have the config Missing

### Recommendation :
1. [L-02] - Replace "lmstudio" with "openai-compatible" and replace url with "http://localhost:1234/v1"
2. [H-09] - Move ToolRegistry to the tools module instead of core
3. [L-03] - This seems to not serve any purpose, we should remove. But if it does have mention elsewhere with purpose this can be halted to confirm if it is actually needed or not.
4. [M-03] - Check on every modules to add their config. context module should also have config to determine when compression happens etc.
Consideration :
Re-check the config against all modules to ensure config are correct and used as expected for every modules.

## Agent
### File Location :
- src/tinycua-sdk/tinycua_sdk/agent

### Question :
-

### Issue :
- [L-04] - LLM Model should be stored in their own class with metadata instead of just str name
- [H-10] - LLM Model is stored directly with Agent
- [M-04] - Long and Short term memory is planned to be generalized into memory that persist across session
- [M-05] - Planning prompt is generally not needed, we only need system prompt to define agent behaviour and user prompt
- [M-06] - Backend is saved in attribute directly 

### Recommendation :
- [L-04] - LLM Model class should consist of all of the model possible metadata such as provider, api_key, base_url, model_name, max_context.
- [H-10] - LLM Model should not be stored directly to agent instead it should have it's own storage like tools etc and it should be plugged-in and out of Agent according to what model the user want to use.
- [M-04] - long term and short term memory should be removed
- [M-05] - Remove planning prompt we only need instruction and system prompt and user prompt during run later
- [M-06] - Remove mode and backend related information then create a BackendKind class which can either be Local or Remote with the same interface so it's easy to change and detect if agent is running local or remote mode. BackendKind should also be storable locally only as it is mostly for client to easily connect to remote or not
Consideration:
Streamline this system because Agent seem to handle too much aspect.
Agent should remain only for agent as minimal as possible such as list of tools, skills, loop etc.
Agent metadata should also be storable to database
We should generally store these as AgentConfig

## Codebase overall
### File Location :
- src/tinycua-sdk/tinycua_sdk

### Question :
-

### Issue :
- [H-11] - Right now we have a lot of effort on "Storing" data but does not seem to have a cannonical loading system
### Recommendation
- [H-11] - We should ensure that every modules that can we stored have a "load" function that can load based on any StorageBackend they have.

## Modeling
### File Location :
- src/tinycua-sdk/tinycua_sdk/modeling

### Question :
-
### Issue :
- [M-07] - Modeling only stored on files

### Recommendation :
- [M-07] - Restructure modeling system to use database as storage instead

## Client
### File Location :
- src/tinycua-sdk/tinycua_sdk/clients

### Question :
-
### Issue :
- [M-08] - Agent Client seems to no longer serve any purpose
- [H-12] - backend.py states "tinycua_sdk.clients.backend is deprecated. Use tinycua.clients.backend instead."

### Recommendation :
- [M-08] - Remove agent client system
- [H-12] - Clarify the needs of client, if not we should probably remove the whole client and rework it from scratch.
