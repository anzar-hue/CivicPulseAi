---
title: CivicPulseAi
emoji: 🏛️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# CivicPulse AI – Smart Civic Complaint Intelligence System

CivicPulse AI is a guided civic complaint platform that helps citizens report real-world issues without needing to understand complex government systems.

It accepts unstructured complaints, detects multiple issues, resolves ambiguity, assigns urgency, and maps them to the appropriate authority — acting as a digital civic desk for everyday users.

---

## Problem

An average citizen faces civic issues daily but often does not know where or how to file a complaint.

Existing systems:
- are fragmented and time-consuming  
- require structured input  
- fail to handle multiple issues in a single complaint  

In reality, a complaint like “road problem” may include:
- potholes  
- illegal construction  
- delayed work  

This gap between real-world problems and structured reporting leads to misrouting, delays, and unresolved issues.

---

## Solution

CivicPulse AI acts as a guided gateway for civic complaints.

It allows users to describe problems naturally and then:
- detects multiple issues  
- handles ambiguity through clarification  
- assigns urgency  
- determines responsibility  
- maps to the correct authority  
- provides a clear next step  

Instead of forcing structured input, the system adapts to how users actually describe problems.

---

## Core Innovations

- Multi-issue understanding within a single complaint  
- Ambiguity handling through clarification questions  
- Transparency in responsibility and authority mapping  

---

## How It Works

1. User writes complaint in natural language  
2. System processes input through structured pipeline  
3. Detects multiple issues if present  
4. Asks clarification if needed  
5. Assigns urgency  
6. Maps issues to relevant authority  
7. Returns structured output with recommendation  

The system functions like a digital civic desk, helping users understand and act on their complaints without navigating complex procedures.

---

## Example

**Input:**  
"There is water leakage and road damage near my house"

**Output:**  
- Issue 1: Water Supply Problem → Jal Nigam  
- Issue 2: Road Damage → PWD  
- Urgency: High  
- Recommendation: Contact respective departments  

---

## System Architecture

The system follows a layered architecture connecting frontend interaction with backend decision logic.

- Frontend captures user complaints in natural language  
- Backend (Flask) processes input through a structured pipeline  
- Rule-based engine performs primary routing using mapping logic  
- LLM (OpenAI-compatible API) acts as fallback for ambiguity and complex cases  

The architecture is currently stable at a **city-level implementation**.  
With integration into government APIs and datasets, it can scale to **state and national levels** without major changes to core logic.

---

## AI Processing Pipeline

The system processes complaints through multiple stages:

- Text preprocessing  
- Signal extraction (keywords, urgency, legal hints)  
- Domain classification (Sanitation, Electricity, Infrastructure)  
- Multi-issue detection  
- Clarification handling  
- Authority mapping  
- Priority ordering  
- Reward evaluation  

This ensures structured and explainable decision-making instead of generic chatbot responses.

---

## Key Features

- Multi-issue detection  
- Ambiguity handling  
- Urgency classification  
- Public vs private ownership detection  
- Authority mapping  
- Rule-based + LLM fallback system  
- Structured output generation  
- Multilingual UI support (English / Hindi / Kannada)  

---

## Backend (OpenEnv Environment)

The backend is implemented as an OpenEnv-based decision environment:

- `reset()` → initializes complaint state  
- `step(action)` → processes decision and returns reward  
- `state()` → returns current environment state  

Flow:  
Observation → Action → Environment → Reward → Next Observation  

This allows structured evaluation and reproducibility of decision-making logic.

---

## Reward System

The reward function is deterministic and reflects decision quality:

- 1.0 → correct domain and authority  
- 0.5 → correct domain but incorrect authority  
- 0.3 → safe handling (clarification / escalation)  
- 0.0 → incorrect handling  

This encourages safe and explainable decisions instead of overconfident errors.

---

## Frontend

The frontend simulates a real civic interaction interface:

- Welcome screen with introduction  
- Slideshow of civic visuals  
- Chat-based complaint interaction  
- Category suggestion buttons  
- Structured output display (issues, urgency, authority, recommendation)  
- Complaint history tracking  

---

## Learning Behaviour (Memory)

The system includes a lightweight memory mechanism:

- Stores previous complaints  
- Retrieves similar cases (`memory_hits`)  
- Assists decision-making  

It does not retrain internally but provides structured signals for external agent learning.

---

## Limitations

- No real-time government system integration  
- Authority routing is simulated  
- Mapping layer is keyword-based (prototype stage)  
- Multilingual output is partially implemented  
- LLM requires API token for advanced behavior  

---

## Future Scope

- Government API integration  
- Real-time complaint tracking  
- Authority assignment and escalation  
- Scheme recommendation system  
- Public data transparency (PDS, budgets, reports)  
- Full multilingual backend support  
- City → State → National scaling  

---

## Business Potential

CivicPulse AI can operate as a collaborative platform:

- Government provides verified data and authority systems  
- Platform provides AI-driven complaint intelligence  
- Revenue via partnerships, licensing, and minimal ads  

It is designed as a **utility-first system**, not an ad-driven product.

---

## Running the Project (Docker)

### Build

```bash
docker build -t civicpulse-ai .