Architecture Specification & Product
Requirements Document (PRD)
Autonomous Agentic GTM Engine & Value-Hook
Pipeline
Target System: ReactFirst AI Proactive Outbound Engine
Document Status: Ready for Implementation / Production-Grade Spec
Author: CTO / Core Architecture Team
Date: June 18, 2026
1. Motivation & Business Context
1.1 Problem Statement
In 2026, consumer-facing industries—specifically FMCG (Fast-Moving Consumer Goods),
Direct-to-Consumer (DTC) fashion, and modern Retail—operate inside incredibly narrow
narrative windows. Traditional cold outbound strategies (e.g., static filtering via LinkedIn
Sales Navigator, generalized email sequences) yield sub-1% reply rates. This failure stems
from a lack of immediate, context-specific value injected at the point of initial contact.
Standard static code pipelines cannot adaptively crawl the web, identify qualitative social
media vulnerabilities, cross-reference them against complex operational constraints, and
programmatically generate bespoke analytical collateral (e.g., tailored Narrative Vulnerability
PDFs) for every distinct brand in real time.
1.2 The Agentic Solution
This document specifies a production-grade, highly autonomous AI Agent that orchestrates
an advanced Go-To-Market (GTM) data pipeline. By combining state-of-the-art Large
Language Models (LLMs), a highly localized hybrid RAG mechanism, robust mathematical
validation layers, and resilient execution loops, the agent autonomously transforms raw
market intent into highly contextualized outbound campaigns.
Instead of waiting for an enterprise to experience a public relations crisis or a narrative shift
passively, this system hunts for high-fit brands, analyzes their public digital footprints in
controlled micro-batches (Chunks), grades their alignment against strict Ideal Customer
Profile (ICP) parameters, pairs them with contextual historical case studies, and calls the
core ReactFirst application API to produce a customized PDF value proposition ready for
automated, multi-channel distribution.
2. Authoritative Data Input Architecture
The agent operates over three strictly bounded data inputs and an explicit GTM instruction
set. The system must treat these sources as the single version of truth, preventing the model
from hallucinating baseline configurations, brand realities, or pricing models from its
pre-trained parametric knowledge base.
+--------------------------------------------------------+
| DATA BASELINE |
+--------------------------------------------------------+
| |
| brands_catalog.csv] ---> Brand Identity & History[ |
| |
| )contacts.json] ---> Target Profiles (CMO/VPM[ |
| |
| gtm_policies.txt] ---> Rule Compliance Matrix[ |
| |
+--------------------------------------------------------+
2.1 Brands Data Catalog (brands_catalog.csv)
This file contains the historical context of existing customers, past opportunities, and
blacklisted entities. It consists of 9 immutable columns:
● Uniq_Id: Primary key (UUID string).
● Brand_Name: Legal and public trading name of the company.
● Primary_Domain: The authoritative root URL (used for web scraping and identity
de-duplication).
● Core_Category: Multi-tier categorization path (e.g., Apparel > Athleisure >
Sustainable).
● Estimated_Ad_Spend_Tier: Annualized digital ad spend matrix (Tier 1: $5M+, Tier
2: $1M-$5M, Tier 3: <$1M).
● Current_Status: Operational state within the ReactFirst ecosystem (Active_Client,
Open_Opportunity, Unreached_Prospect, Blacklisted).
● Historical_Social_Incidents: Integer counting past viral narrative crises or PR
vulnerabilities tracked.
● Main_Competitor_Id: Foreign key pointing to the primary competitor's Uniq_Id.
● Gtin_Prefix: Global Trade Item Number block identifying their product lines.
2.2 CRM Contact Store (contacts.json queried via lead_store.py)
To mimic a live MongoDB instance while eliminating network overhead and container
management during rapid deployment cycles, contact records are handled via mongomock
in-memory structures initialized through an import-safe data loader:
Python
lead_store.py #
import json
import mongomock
collection_instance = None_
:)(def get_lead_data_collection
global _collection_instance
:if _collection_instance is None
)(client = mongomock.MongoClient
]'db = client['gtm_db
]'collection_instance = db['contacts_
:with open('contacts.json', 'r') as f
)data = json.load(f
)collection_instance.insert_many(data_
return _collection_instance
Each record conforms to the following strict JSON schema structure:
JSON
{
,"#schema": "http://json-schema.org/draft-07/schema$" 
,"title": "ContactRecord"
,"type": "object"
{ :"properties"
,} "first_name": { "type": "string"
,} "last_name": { "type": "string"
,} "email": { "type": "string", "format": "email"
,} "corporate_access_key": { "type": "string"
,} "role": { "type": "string"
,} "linkedin_url": { "type": "string", "format": "uri"
,} "interaction_history_count": { "type": "integer"
,} "opt_out_status": { "type": "boolean"
} "target_brand_id": { "type": "string"
,}
required": ["first_name", "last_name", "email", "corporate_access_key", "role","
]""target_brand_id
}
2.3 GTM Operational Policies (gtm_policies.txt)
An absolute instruction matrix parsed by the agent before finalizing any outbound execution
state:
1. Authoritative Context Bound: Any claim regarding a prospect's market position,
tier, or competitor layout must derive solely from brands_catalog.csv.
2. ICP Validation Threshold: A prospect brand is qualified for automated outreach if
and only if it explicitly ticks $\ge 3$ strict qualification parameters during deep
scraping.
3. The Premium Pricing Tier Tiering Loop: Prospects belonging to companies with an
Estimated_Ad_Spend_Tier of Tier 1 qualify for the enterprise custom platform SLA.
If their historical tracked incidents exceed 5, a premium risk multiplier of 15% is
programmatically added to their internal value estimation calculation.
4. Data Protection & Authentication Gate: The corporate_access_key must be
verified through the authentication tool before extracting or modifying private contact
records or logging past interaction counts.
5. Output Suggestions Ceiling: When generating recommendations or matches, the
agent must output no more than 3 distinct target angles or product capabilities. If a
query requests a specific subset (e.g., "top 2 items"), the agent must output exactly
that count.
6. Explicit Zero-Match Boundary: If no prospect matches the criteria or if the pipeline
parameters fail validation, the agent must bypass all generative prose and return
exactly the string: "We have no product available today that fits your request".
3. Multi-Modal Agentic Core & Tool Topology
The architecture separates the discovery phase from the analytical execution loop. It relies
on explicit tool schemas specifying detailed input boundaries to eliminate token wastage and
prevent the agent from getting stuck in iterative execution loops.
=========================================================================
===============
PHASE 1: THE DISCOVERY & 3-WAY FAN-OUT ENGINE
=========================================================================
===============
)Trigger Query] ---> (Adaptive Query Generator: Gemini Flash[
|
+--------------------+--------------------+
| | |
v v v
]Gemini Discovery] [SerpAPI + Maps] [Tavily Recovery[
)gemini-3.1-lite) (Local/Organic) (Fallback Engine(
| | |
+--------------------+--------------------+
|
v
]Lead Extractor & Scorer[
)gpt-4o-mini(
|
v
Raw Unverified Target Pool
=========================================================================
===============
PHASE 2: THE DURABLE BATCH ENRICHMENT SWARM & VALUE HOOK
=========================================================================
===============
Raw Unverified Target Pool
|
v
]Controlled Micro-Batches[
)Leads / Chunk 100(
|
+--------------------+--------------------+
| )Time Budget: 800s Per Step Execution( |
+--------------------+--------------------+
|
v
]Company Analyzer[
)gpt-5-mini + Firecrawl(
|
v
]Tag Evaluator[
)ICP Filter Constraints Check(
|
v
]Solicitation Angle Matcher[
)RAG: Hybrid Vector + BM25(
|
v
]Profile Expander/API[
)Apollo/Prospeo + ReactFirst(
| 
v
Programmatic Core Production PDF
3.1 Phase 1 Tooling: The Adaptive Discovery & 3-Way Fan-Out
Tool 1: generate_search_queries
● Execution Environment: Gemini Flash Latest
● Purpose: Generates a matrix of 10 to 20 highly granular, non-overlapping search
query variations based on an amorphous vertical input descriptor.
● JSON Schema Spec:
JSON
{
,"name": "generate_search_queries"
description": "Transforms high-level market vertical definitions into 10-20 distinct, targeted"
,".search queries to capture niche industry footprints. Use when initial seed datasets are low
{ :"parameters"
,"type": "object"
{ :"properties"
vertical_seed": { "type": "string", "description": "The base sector, e.g., 'sustainable footwear"
,} "'Europe
} target_count": { "type": "integer", "default": 15"
,}
]"required": ["vertical_seed"
}
}
Tool 2: execute_3way_fanout
● Execution Environment: Concurrent multi-model execution pool.
● Purpose: Executes the search query array simultaneously across three distinct
discovery vectors to guarantee deep market scraping containment.
● Mechanics:
1. Vector A (Gemini Discovery): Calls gemini-3.1 flash-lite with web grounding
enabled to extract lists, press releases, and structured industry indices.
2. Vector B (SerpAPI + Maps): Pulls raw Google Search and localized Maps
node arrays to identify local physical retail presence and core domain
references.
3. Vector C (Tavily Recovery): Acts as a dynamic fallback engine. If Vector A
and Vector B yield fewer than 2 structural domains for a given query line,
Tavily is triggered automatically with specialized research switches enabled to
uncover niche DTC brands.
● JSON Schema Spec:
JSON
{
,"name": "execute_3way_fanout"
description": "Executes concurrent parallel queries across Gemini Discovery, SerpAPI, and"
,".Tavily Recovery fallback paths to maximize target yield
{ :"parameters"
,"type": "object"
{ :"properties" 
{ :"queries"
,"type": "array"
,} "items": { "type": "string"
".description": "List of validated search query strings generated by the Query Generator"
}
,}
]"required": ["queries"
}
}
Tool 3: extract_and_score_pool
● Execution Environment: gpt-4o-mini
● Purpose: Compiles all discovery raw data arrays, eliminates domain duplicates
(De-duplication layer), and maps them against raw historical vectors from
brands_catalog.csv to output a clean list of candidate companies.
3.2 Phase 2 Tooling: The Durable Enrichment Swarm & Core PDF
Generation
To protect enterprise resources from thread exhaustion and rate limits, the agent processes
candidates in deterministic micro-batches: 100 leads per chunk, allocating a strict time
budget of 800 seconds per chunk execution step.
Tool 4: analyze_company_chunk
● Execution Environment: gpt-5-mini + Firecrawl API
● Purpose: Crawls the targets' root domains to extract tech stack metadata (detecting
if the TikTok Pixel, Meta Pixel, or Google Tag Manager are present) and text patterns
to determine their operational scale.
● JSON Schema Spec:
JSON
{
,"name": "analyze_company_chunk"
description": "Processes a controlled batch of exactly 100 domain entries. Crawls homepages"
,".and legal footprints using Firecrawl to identify pixel configuration and operational data
{ :"parameters"
,"type": "object"
{ :"properties"
{ :"domains"
,"type": "array"
,} "items": { "type": "string"
".description": "Array of exactly or up to 100 unverified target root domains"
}
,}
]"required": ["domains"
}
}
Tool 5: evaluate_icp_tags
● Execution Environment: Structural JSON Classifier Rule Engine.
● Purpose: Validates the extracted metadata against the qualifying criteria specified in
Policy 2 ($\ge 3$ matching tags required for automatic qualification).
● JSON Schema Spec:
JSON
{
,"name": "evaluate_icp_tags"
description": "Applies a strict boolean filter across company profiles. Only companies meeting 3"
,".or more defined ICP tags are qualified for programmatic PDF generation
{ :"parameters"
,"type": "object"
{ :"properties"
{ :"company_profile_data"
,"type": "string"
".description": "The raw text and technical string metadata extracted during the crawl step"
}
,}
]"required": ["company_profile_data"
}
}
Tool 6: match_solicitation_angle
● Execution Environment: Local Vector Index (ChromaDB + all-MiniLM-L6-v2) +
Reciprocal Rank Fusion (RRF).
● Purpose: Executes a local hybrid RAG query combining semantic embeddings
(representing the company's messaging vulnerabilities) with exact string matching
(BM25) against ReactFirst's library of past historical crisis case studies. This process
classifies the account into one of 4 specific outreach priority tiers (Tier 1: Critical Fit to
Tier 4: No Match).
● JSON Schema Spec:
JSON
{
,"name": "match_solicitation_angle"
description": "Performs an RRF hybrid vector search against past enterprise case studies to"
,".map out the exact outbound hook angle based on discovered public vulnerabilities
{ :"parameters"
,"type": "object"
{ :"properties"
scraped_narrative_context": { "type": "string", "description": "The textual core messaging"
,} ".extracted from the target company's site
category_path": { "type": "string", "description": "Authoritative category matching from the"
} ".CSV database
,}
]"required": ["scraped_narrative_context", "category_path"
}
}
Tool 7: request_reactfirst_pdf
● Execution Environment: Programmatic System Runtime Client.
● Purpose: Executes a direct API call to the core ReactFirst application instance,
triggering the generation of a specialized Narrative Analysis PDF report for the
verified domain. It saves the resulting artifact directly to the workspace storage layer.
● JSON Schema Spec:
JSON
{
,"name": "request_reactfirst_pdf"
description": "Communicates directly with the ReactFirst product backend via secure API to"
,".generate and store the value-hook analysis PDF asset
{ :"parameters"
,"type": "object"
{ :"properties"
,} "target_domain": { "type": "string"
,} "validated_angle_key": { "type": "string"
} "calculated_risk_score": { "type": "number"
,}
]"required": ["target_domain", "validated_angle_key", "calculated_risk_score"
}
}
Tool 8: secured_calculator
● Execution Environment: Python AST Isolated Walk Engine.
● Purpose: Evaluates premium pricing increments and risk tier offsets (Policy 3)
without introducing arbitrary code execution vulnerabilities. Raw eval() or exec()
loops are strictly prohibited.
● Implementation Standard:
Python
import ast
import operator
:class SafeCalculator
{ = ALLOWED_OPERATORS
,ast.Add: operator.add
,ast.Sub: operator.sub
,ast.Mult: operator.mul
,ast.Div: operator.truediv
ast.USub: operator.neg
}
classmethod@
:)def evaluate(cls, expression_str: str
)'tree = ast.parse(expression_str, mode='eval
)return cls._walk(tree.body
classmethod@
:)def _walk(cls, node
:)if isinstance(node, ast.Num
return node.n
:)elif isinstance(node, ast.BinOp
)left = cls._walk(node.left
)right = cls._walk(node.right
)op_type = type(node.op 
:if op_type in cls.ALLOWED_OPERATORS
)return cls.ALLOWED_OPERATORS[op_type](left, right
:)elif isinstance(node, ast.UnaryOp
)operand = cls._walk(node.operand
)op_type = type(node.op
:if op_type in cls.ALLOWED_OPERATORS
)return cls.ALLOWED_OPERATORS[op_type](operand
)"}raise ValueError(f"Unauthorized mathematical syntax block: {node
4. Execution Flow Topology & Conversational Triggers
To illustrate the behavioral sequencing of the system, the following table charts how specific
incoming business queries map directly to specific backend tools, ensuring complete rule
compliance at every stage.
# Incoming System
Query Sample
Target
Architectural
Path &
Execution
Steps
Primary Tool Chain
Q1 "My access key is
Access99 and my
contact email is
cmo@nordicwear.com.
We have experienced 6
high-profile public
incidents this year and
our ad spend tier is Tier
1. What is our premium
estimation tier, and is
there a localized asset
ready?"
1. Authenticate
contact and
cross-reference
records via
lead_store.py.
2. Read Policy 3
(Premium risk
threshold
calculation
loop).
3. Compute
current
estimation
pricing tier plus
15% risk
increment using
authenticate $\rightarrow$
get_lead_data_collection
$\rightarrow$
secured_calculator
the isolated
calculator.
4. Retrieve
existing brand
asset matches.
Q2 "What are the structural
profile differences
between Brand_Id_01
(Apparel) and
Brand_Id_02 (Footwear)
in terms of digital ad
footprints?"
1. Read catalog
boundaries.
2. Fetch
structural
columns for both
entries.
3. Generate a
clean markdown
table comparing
categories,
domains, and
competitor
metrics.
brands_catalog parsing via
pandas
Q3 "Find apparel brands with
an annual ad spend tier
under Tier 2 that exhibit
specific semantic
weaknesses around
ethical sourcing
messaging."
1. Apply a hard
column filter on
the CSV data
source.
2. Pass resulting
domain
frameworks to
the local RAG
vector space to
surface
companies
displaying
relevant
thematic
messaging
gaps.
filter_products
$\rightarrow$
match_solicitation_angle
(Hybrid RAG)
Q4 "I want to track emerging
cosmetic lines using
sustainable packaging
that don't have any
current active Meta
tracking codes running."
1. Execute the
3-Way Fan-Out
engine to
discover new
domains.
2. Use the
durable
processing
engine to check
pixel setups in
chunks of 100.
generate_search_queries
$\rightarrow$
execute_3way_fanout
$\rightarrow$
analyze_company_chunk
3. Filter out
domains with
active tracking.
Q5 "Give me a list of the top
5 brands most vulnerable
to upcoming TikTok
algorithm updates."
1. Identify
relevant
records.
2. Intercept
output
constraints
using Policy 5.
3. Cap
generative lists
at exactly 3
results,
overriding the
user's initial
request for 5.
Internal System Prompt
Rule Containment
Q6 "We need to hunt down
micro-influencer brands
in the coffee niche that
have no current products
in our historical catalog
database."
1. Generate
search matrix.
2. Run 3-way
scraping loop.
3. Check results
against the
authoritative
execute_3way_fanout
$\rightarrow$ Return exact
fallback: "We have no
product available today that
fits your request"
CSV catalog. If
none exist and
scraping fails to
meet the
criteria, apply
Policy 6.
5. Architectural Guardrails & Resiliency Patterns
To ensure this system operates safely and effectively within a lean engineering environment,
it includes three foundational guardrails directly in its design.
5.1 Tool Gateway Validation Pattern
Every structural payload returned by the agent loop that targets external interaction
infrastructures (e.g., passing lead objects to Smartlead or updating the production database
workspace) must clear a strict gateway abstraction layer.
● This layer runs validation tests to ensure no fields contain null objects, strings match
target formatting regexes perfectly, and generated PDFs exist in storage with valid
headers before executing a step.
+-----------------------------------+
| AGENT LOOP OUTPUT |
+-----------------------------------+
|
v
+-----------------------------------+
| TOOL GATEWAY VALIDATION |
| |
| Check for Null Objects ]*[ |
| Validate String Format Regex ]*[ |
| Verify PDF Structural Health ]*[ |
+-----------------------------------+
|
+-----------------+-----------------+
| |
]Valid Payload] [Invalid Payload[
| |
v v
+---------------------------+ +---------------------------+
| EXECUTED OUTBOUND ACTION | | ABORT & RAISE RECOVERY |
+---------------------------+ +---------------------------+
5.2 Trust-Gated Autonomy
Prospects that clear the structural evaluate_icp_tags processing layer with a borderline
rating (e.g., companies that meet exactly 3 criteria but score low on traffic indicators) are
barred from proceeding immediately to automated email delivery.
● Instead, the system routes these entries to a specific Slack channel via webhook,
allowing a human growth operator to approve or discard the target with a single click.
This creates a secure, human-in-the-loop framework for ambiguous data points.
5.3 Technical System Bounds & Anti-Loop Safeguards
● Global Step Cap: Any single query execution path entering answer_question is
restricted to a maximum of 15 iterative tool calls. If the agent fails to reach a definitive
final answer within 15 turns, it must stop processing and fall back to a safe error
state.
● Network Isolation Constraints: Production outbound campaigns must use
dedicated tracking sub-domains (outreach.reactfirst.ai) to keep cold outreach
volume completely separated from the company's core corporate email domain
infrastructure.
● Rate and Volume Envelope: Outbound email tools are throttled at a strict maximum
of 50 messages per day per active outbound inbox.
6. Analytical Engineering Metrology (System Validation
Formulas)
The success and operational quality of this agentic pipeline are measured using precise
engineering metrics, avoiding vague vanity benchmarks like total email volume or raw click
counts.
6.1 Pipeline Value Generation Velocity ($V$)
Measures the velocity at which the agent injects qualified, high-value opportunities into the
CRM pipeline. This is heavily optimized by automating asset preparation and cutting down
total cycle time:
$$V = \frac{N \times W \times A}{T}$$
Where:
● $N$ = Total number of verified ICP opportunities surfaced and processed by the
agent.
● $W$ = Historic close rate percentage of value-hook outreach methodologies.
● $A$ = Average Annual Contract Value (ACV) of the ReactFirst enterprise
subscription model.
● $T$ = Total sales cycle length measured in days.
6.2 Cost Per Validated Learning ($C_{\text{VL}}$)
Quantifies the operational cost efficiency of running automatic market discovery cycles
across new verticals compared to hiring manual research agencies:
$$C_{\text{VL}} = \frac{C_{\text{infra}} + C_{\text{tokens}} +
C_{\text{scraping\_credits}}}{N_{\text{experiments}}}$$
Where:
● $C_{\text{infra}}$ = Baseline host computing costs.
● $C_{\text{tokens}}$ = Direct LLM context window input/output token costs (OpenAI +
Gemini endpoints).
● $C_{\text{scraping\_credits}}$ = Firecrawl and SerpAPI query usage expenditures.
● $N_{\text{experiments}}$ = Number of distinct sub-vertical market discovery loops
successfully executed.
6.3 Signal-To-Campaign Latency ($L_{\text{signal}}$)
Tracks the responsiveness of the system by measuring the total time elapsed from initial
discovery to delivery of the personalized value proposition:
$$L_{\text{signal}} = T_{\text{delivery}} - T_{\text{discovery}} \quad \left( \text{Target
Boundary Condition: } L_{\text{signal}} \le 900\text{ seconds} \right)$$
7. Standard Operating Procedure (SOP) Checklist
Developers must verify all items on this checklist before pushing code changes to
production:
● [ ] Schema Conformance: Verify that the payload structure returned by
get_lead_data_collection maps directly to the mongomock storage layout without
altering the original keys.
● [ ] Isolated Calculation Testing: Validate that passing complex mathematical
expressions (e.g., (1700 + 450) * 1.15) to SafeCalculator evaluates correctly, and
that any string containing characters outside the approved AST whitelist raises an
immediate ValueError.
● [ ] Strict String Fallback: Confirm via automated integration tests that any query
producing an empty result set yields exactly the string "We have no product
available today that fits your request", with no additional punctuation, spaces, or
generative text.
