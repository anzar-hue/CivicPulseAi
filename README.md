---
title: CivicPulseAi
emoji: 🏛️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---






# CivicPulse AI – OpenEnv Civic Grievance Decision Environment
## 🐳 Running with Docker

This project includes a Dockerfile so that the entire application can run without manually installing dependencies.

### Build the Docker Image

docker build -t civicpulse-ai .
### Run the Application
docker run -p 7860:7860 civicpulse-ai
### Open in Browser

Once the container is running, open:

http://localhost:7860

### Environment Variables
To use the AI features, create a `.env` file in the root directory:

HF_TOKEN=your_api_key_here
MODEL_NAME=openai/gpt-oss-20b
API_BASE_URL=https://router.huggingface.co/v1

Note: The system will still work using rule-based logic if the API key is not provided.
### Why Docker?

Docker makes it easy to run this project on any system without worrying about setup.  
Everything (backend, frontend, dependencies) runs inside a single container.

## Problem Statement

Unstructured civic complaints often lead to incorrect routing, delays, 
and unresolved issues due to unclear information, multiple problems in 
one message, and lack of intelligent prioritization.
This project models civic grievance handling as a structured decision
environment where an agent must interpret complaints, ask clarification, 
and route them correctly.


## Solution

CivicPulse AI converts raw civic complaints into structured decisions.
It identifies issues, assigns urgency, determines ownership (public/private), 
and routes the complaint to the correct authority. It also asks clarification 
questions when the complaint lacks sufficient detail.
This system is designed not just as an application, but as an environment for 
evaluating and improving decision-making agents.

## How to Run 
- Run the backend: python app.py  
- The application runs on port 7860 (frontend and backend are integrated)  
- Open http://localhost:7860 in your browser  

## AI System Overview

The system processes complaints through multiple steps:
- Text preprocessing  
- Signal extraction (keywords, urgency, legal hints)  
- Domain classification (Sanitation, Electricity, Infrastructure)  
- Issue detection (single or multiple)  
- Clarification (if needed)  
- Authority mapping  
- Priority ordering  
- Reward evaluation  
This ensures structured and explainable decision-making instead of random chatbot responses.


## Tools Used

- Python  
- Flask (backend API)  
- OpenEnv framework  
- Hugging Face / OpenAI-compatible API  
- Pydantic (typed models)  
- HTML, CSS, JavaScript (frontend)  


## Backend (OpenEnv Environment)

The backend is implemented as an OpenEnv environment with:
- `reset()` → initializes complaint state  
- `step(action)` → processes agent decision  
- `state()` → returns current environment state  
The environment fully follows OpenEnv specifications with typed models and deterministic evaluation.


### OpenEnv Interaction Loop

The environment follows a standard agent loop:
- reset(complaint) → initializes the environment  
- step(action) → evaluates the decision and returns reward  
- state() → returns current state  

Flow:  
Observation → Action → Environment → Reward → Next Observation  


## Working Terminology

- HF Token → Used for accessing LLM APIs  
- LLM Fallback → Rule-based logic used when LLM fails  
- Observation → processed complaint data  
- Action → structured decision output  
- Reward → score assigned to action  


## Reward System

The reward function is deterministic and provides partial credit:
- 1.0 → correct domain and authority  
- 0.5 → correct domain but incorrect authority  
- 0.3 → safe handling of ambiguous cases (clarification / escalation)  
- 0.0 → incorrect handling  
This reward design reflects real-world decision quality, where partially correct 
actions are still valuable and safe handling is preferred over confident mistakes.


## Frontend

The frontend simulates a real civic interaction interface where users can submit 
complaints and receive structured decisions.
It includes:
- Welcome screen with system introduction  
- Complaint category selection  
- Chat-based interaction  
- Structured output display (issues, urgency, authority, recommendation)  


## Learning Behaviour (Memory)

The system includes a lightweight memory mechanism.
It stores previous complaints and retrieves similar cases (`memory_hits`) to assist 
in decision-making.
While it does not retrain model weights internally, it provides:
- structured observations  
- deterministic rewards  
- reproducible tasks  
An external agent can use these signals to improve decision-making over time.


## Limitations

- No real-time government system integration  
- Limited to predefined domains  
- Memory is not a full learning system  
- LLM may fail without valid API token  


## Scope / Feasibility

- Can integrate with government complaint systems  
- Supports multilingual expansion  
- Can evolve into a full complaint tracking platform  
- Suitable for real-world civic automation 

# Future Features

- Ai action layer(sends emails to dept and follows up complaints)
- More interactive
- Broaden complaint areas
- Image upload and Image analyzation by Ai 


## Conclusion

CivicPulse AI demonstrates how real-world civic complaint handling can be transformed
into a structured decision environment.
It bridges rule-based reasoning and AI-assisted processing to enable reliable, 
explainable, and scalable agent evaluation.