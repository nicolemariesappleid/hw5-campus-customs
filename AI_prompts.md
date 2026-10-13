# AI Prompts Log — HW5 (Campus Customs)

A log of the prompts I typed to the AI, word for word. One section per problem.

---

## Problem 1 — Project Setup (database working copy, Portkey config, prompt log)

**Prompt:**

> Let's start a new vibecoding project. the attached file is the original shop database. make a copy of the database file called data/campus_customs_new.db and point the MCP server and backend at that working copy. keep campus_customs.db untouched so that I can reset when I want to start resolving tickets. use my PORTKEY_API_KEY for ai calls. use only gpt-6-luna through portkey for every agent. start by making a folder called hw5 to keep all of this project in, and creating AI_prompts.md inside it. this is a log of what i type to you (prompts). put one section for each problem 1-11. each section must include the problem number and title, at least one prompt I typed in my own words (no summary) and a follow up prompt if i needed it. this prompt is problem 1.

**Follow-up prompt:**

> _(none yet)_

---

## Problem 2 — Explore the Database and Start the Harness

**Prompt:**

> here's problem 2. open data/campuscustoms.db and look through every table and its fields. copy the original file to data/campus_customs_new.db . later problems will update that working copy. start output/harness.md . For each table, list the fields and one short line on why that table matters for the agents.

**Follow-up prompt:**

> 

---

## Problem 3 — Build the MCP Server (3 Tools)

**Prompt:**

> here's problem 3. write an mcp server in mcp_server/ using FastMCP. it will talk to data/campus_customs_new.db . you do not need to connect or run it in this problem. it's important that every agent in this homework uses the tools in this mcp server. for now, write 3 tools you know you will need for the tickets in the database. keep the names clear. never invent any data, only use information in the database. in output/harness.md , list each of your 3 MCP tools. for each too include which table it reads, whic ticket it helps unlock (101, 102, or 103) and one sentence on why that tool is the right one for that ticket. be very specific. tie each tool to the ticket  . then add a short mcp_server/README.md file that explains what the mcp server is for, which database file it uses, and the 3 tools it has

**Follow-up prompt:**

> 

---

## Problem 4 — Connect the MCP Server and Smoke Test the Tools

**Prompt:**

> this is problem 4. add your mcp server in this vibecoder to this project so the vibe coder can call the tools. save the connection JSON text in .mcp.json at the project root or however you save local mcp server lists. with you connected, test each of your 3 mcp tools. save the evidence in output/mcp_smoke.json . for every tool include the prompt i asked the vibe coder, the tool name, and the tool output, which must match values in data/campus_customs_new.db

**Follow-up prompt:**

> 

---

## Problem 5 — Build the Agent Team (PydanticAI)

**Prompt:**

> this is problem 5. build the agentic team for campus customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. include prompts, models and agent loops so that they can delegate work to each other with full connectivity. put the agent prompts one file per agent in backend/prompts/ . put data types in backend/models.py and the agent files under backend/ . layout isn't important so long as 5 roles are clear. use my PORTKEY_API_KEY and once again only gpt-6-luna for each agent. here are the prompts with the shop rules that each agent needs: the boss agent reads each ticket, decides who should work on it, and delegates,  and makes final calls once other agents have done their tasks; the inventory agent will check stock by both SKU and size, spot any shortfalls, and figure out which vendor can restock; the accounting agent watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval; the facilities agent handles the shop space side, including leases, rent, utilities, and anything else you think might be relevant; and the customer service agent will draft messages for customers but DOES NOT SEND THEM. if any of these agents struggles to complete a task in isolation they can ask any other agent for help but the boss agent still makes final calls. now add any tools these agents need to work on the open tickets to the MCP server. shop facts come from the mcp server over data/campus_customs_new.db . do not invent a second shop-tools layer that bypasses MCP . wire the agents so they append to output/audit_trail.json as they run. for each agent-loop step, record enough to audit later. append to this file and don't wipe it each run. in output/harness.md list each agent and each mcp tool including ones you add in this problem along with which table the tool uses. also add a short safety section which includes any guardrails a real business would want when agents touch real customers and real money. plus limits that keep token use in check. this is very very important i want this homework to use as few token as possible; don't be wasteful!!! minimize!!! finally update mcp_server/README.md so the tool list matches what we now have.

**Follow-up prompt:**

> 

---

## Problem 6 — Expected Team Behavior (desk_tickets.html)

**Prompt:**

> this is problem 6. before wiring the backend, write down what I expect the team to do on each open ticket: I expect the boss to do an initial read of the ticket, determine what the task requires, assign the fulfillment of each of those requirements to the remaining 4 agents, and then for each to complete their relevant task. finally, once each has done their task, or requested help and troubleshot with another agent, the boss will do a final audit determining the ticket was correctly executed. build output/desk_tickets.html as a page I can double-click with one tab per ticket (101, 102, 103). Also add empty cash and reflection tabs for later problems; you can leave thosee blank for now. on each ticket tab fill an expected section only. leave a placeholder for an actual section you will fill after you later run the agents. for each ticket's expected section write my thoughts on who the boss should call first and why, all the agent delegations you expect, and which mcp tools I expect that run to use. not every specialist should be used on every ticket. here are my thoughts: ticket 101 i think the boss will call the inventory specialist to use the check inventory skill and the customer service agent to handle the overdue invoice; ticket 102 will call the accounting specialist and the facilities agent to handle rent; they will use the get_lease tool, and ticket 103 the boss will call the inventory and accounting specialists to take inventory and record margins

**Follow-up prompt:**

> 

---

## Problem 7 — Backend API (FastAPI)

**Prompt:**

> this is problem 7. my react frontend dashboard which i will build in the next problem needs a backend that it can call. in backend/main.py use FaastAPI and add routes that do the following: return the 3 tickets and whether each is open or resolved, take a ticket id and run your agent team on that ticket, return recent agent events including what each agent said and which tools they used so the board can refresh, approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash), return the curent checking balance from cash_accounts, reset the database to the original values when you want to try a fresh run. from the backend/ folder start the server with: uvicorn main:app --reload --port 8000 . in output/harness.md , list each route in one line including what URL and what it does. Importantly, there will be no actual money transactions in this shop, it is fake. make sure there are no emails being sent and no money being transacted.

**Follow-up prompt:**

> 

---

## Problem 8 — Frontend Dashboard (React + Vite + TypeScript)

**Prompt:**

> this is problem 8. build the frontend dashboards in frontend/ with reach and vite and typescript. the page should call the routes you built in problem 7. the board should list all 3 tickets, let you pick one ticket and start the agent team on it, show each agent and what they are saying / doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a pay or purchase when asked, show the chekcing balance (for example it should drop after an approved pay). make the dashboard clean and aesthetically pleasing. let's model it on the headspace app with little bubbly cartoon agents that look cute and talk in speech bubbles. soft lines and squishy vibes. tell the front end to talk to my backend at http://localhost:8000 on the backend allow the vite page origin so the browser is allowed to call those routes then start the board with npm run dev . finally write output/design.md with what I chose for the dashboard look ( layout, how the agents read differently how resolved tickets and cash show up) and why

**Follow-up prompt:**

> 

---

## Problem 9 — Full Run, Actual vs. Expected, Cash Reconciliation

**Prompt:**

> before testing the agents on a full run over the 3 tickets, reset the working database data/campus_customs_new.db again so we can start clean. note the starting checking balance. then run all 3 tickets on the board until each is resolved. open output/desk_tickets.html from problem6. on each ticket tab, fill the actual section from this run: which agents worked, what they delegated, and which tools they used. keep the expected section filled out earlier so that I can compare the two. on the cash tab of the same output/desk_tickets.html , itemize the money, including starting checking balance (after the reset), for each ticket how cash changed when that particular ticket resolved and why (which pay / purchase, dollar amount), and ending checking balance which must match cash_accounts in the working database. make sure the math is correct, build in a double check. also save output/resolved_tickets.json for each ticket, including id, final status, short outcome, what each agent contributed, and any human approvals and output/resolved_board.html which is a page you can double-click with a screenshot of your react board for each resolved ticket. append real runs to output/audit_trail.json and finish output/harness.md so it covers tables, mcp tools, the five agents, API routes, the dashboard, and safety rules.

**Follow-up prompt:**

> explain how to do this When you run `python scripts/full_run.py` somewhere Portkey works, it fills those in, plus the Actual and Cash tabs in `desk_tickets.html`. Then commit and push again so the repo has the real results.

---

## Problem 10 — Reflection

**Prompt:**

> open output/desk_tickets.html and fill the reflection tab. answer in a detailed and thorough manner: how would you evaluate the performance of hte agents on each ticket and why? for each ticket how did actual compare to the expected plan you wrote earlier? what would have been sipler as one agent with tools and why? describe three new problems the shop campus customs might face that this agent team could solve with t he tools you built and describe three new problems the shop campus customs might face that this agent team could NOT solve with the tools you built and explain what kinds of tools and agents you'd need to solve them. tie every answer to this app and the 3 tickets you ran, use the ticket tabs and cash tab on the same page as evidence. no generic ai- sounding essays, i want lots of campus customs details, so do a quick search on campus customs (it's similar to its competitor yale bookstore) to make sure you can make this as detailed as possible

**Follow-up prompt:**

> that last message was problem 10

---

## Problem 11 — Push to a Public GitHub Repo

**Prompt:**

> now for problem 11 we need to push my code to a public github repository. i need the repo url copyable here and also input to output/github_url.txt do NOT push my real .env to the github repo but include both database files under data/ (both the original and working copy). Here's the attached expected file layout. also the README should explain copy original DB to the working copy when I need a clean run, start MCP server, start FastAPI backend, start the react board, reset the DB before a full 3-ticket run.

**Follow-up prompt:**

> done
