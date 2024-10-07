# Multi-Agent AI System for Football Betting Analysis

## Overview

This repository contains scripts for an AI-driven system that analyzes NFL and college football games to generate betting insights. The system uses multiple AI models (Claude Sonnet 3.5) and real-time data collection (web scraping and Perplexity API) to produce comprehensive game assessments and betting recommendations.

## System Architecture

### Data Collection and Processing

1. **NFL Data**:
   - Scrapes advanced analytics from Sumer Sports using Selenium
   - Extracts Pro Football Focus (PFF) data through HTML parsing
   - Retrieves real-time odds using Perplexity API

2. **College Football Data**:
   - Scrapes game stats from Game on Paper
   - Collects real-time odds and team information using the Perplexity API

3. **Data Structuring**:
   - Implements custom JSON schemas for consistent data representation

### Multi-Agent AI Analysis Framework

This system employs several instances of advanced language models to simulate a panel of expert analysts. This approach aims to reduce individual model biases and capture a wider range of insights.

#### 1. Quantitative Analysis (Claude 3.5 Sonnet)

- Processes game data, advanced statistics, and historical performance metrics
- Generates analysis of team strengths, weaknesses, and key matchups

By incorporating a range of advanced metrics (e.g., DVOA, EPA, Success Rate), this analysis provides a nuanced understanding of team performance beyond traditional statistics, potentially identifying opportunities overlooked by conventional analysis.

#### 2. Real-Time Qualitative Analysis (Perplexity AI)

- Provides current insights on team news, player status, and contextual factors
- Analyzes recent team performance, coaching strategies, and environmental conditions

This component captures recent news and contextual factors that may not be reflected in historical data or quantitative metrics, allowing for more timely and informed decision-making. These factors, such as fan sentiment, may not be represented in the quantitative analysis. 

#### 3. Lineup Analysis (Claude 3.5 Sonnet, NFL only)

- Evaluates team rosters, focusing on player grades, positional rankings, and matchups
- Assesses the impact of injuries, substitutions, and tactical formations

By analyzing specific player matchups and team compositions, this module can identify tactical advantages or vulnerabilities that may not be apparent in aggregate team statistics.

#### 4. Expert AI Agents (Multiple Claude 3.5 Sonnet Instances)

- Deploys 5 independent AI "experts", each analyzing the compiled data
- Each agent generates betting recommendations with detailed justifications

This approach simulates a panel of human experts, potentially uncovering insights that a single model might miss. The diversity of analyses helps to reduce the impact of any individual model's biases or oversights. Temperature is set to 0.1. 

#### 5. Consensus Generation (Claude 3.5 Sonnet)

- Aggregates and analyzes the recommendations from all expert AI agents
- Produces a final consensus recommendation for Moneyline, Spread, and Total bets

By synthesizing multiple expert opinions, this meta-analysis can identify areas of strong agreement or noteworthy disagreement, potentially leading to more robust betting recommendations.

### Betting Logic

- Implements the Kelly Criterion for optimal bet sizing
- Uses a custom unit system (0-5) for bet strength recommendations
- Considers market efficiency to identify potential value opportunities

### Output Generation and Distribution

- Uses Claude 3.5 Sonnet for natural language generation of bet summaries
- Integrates with Discord API for automated result posting

## Technical Innovations

### 1. Multi-Agent Consensus Approach

Our system's use of multiple AI agents to analyze the same data from different perspectives is inspired by ensemble learning techniques in machine learning.

**Potential Accuracy Improvements**:
- Reduced impact of individual model biases
- Increased robustness to outliers or anomalous data
- Ability to capture subtler patterns through diverse analytical perspectives

### 2. Combined Quantitative-Qualitative Analysis

By merging statistical analysis with real-time qualitative insights, our system aims to provide a more comprehensive betting strategy.

**Potential Accuracy Improvements**:
- More holistic game assessment, considering both data and context
- Ability to adapt to dynamic factors not captured in historical data
- Potential to identify value bets where qualitative factors are over- or under-valued by the market

### 3. Natural Language Processing for Sports Analysis

Our use of advanced language models (Claude 3.5 Sonnet) for sports analysis expands the application of NLP in this domain.

**Potential Accuracy Improvements**:
- Sophisticated interpretation of complex sports statistics and terminology
- Ability to extract insights from unstructured text data (e.g., news articles, injury reports)
- Generation of more coherent and contextually relevant betting narratives

## Conclusion

This project applies advanced AI techniques to sports betting analysis. By using a multi-agent approach, incorporating diverse data sources, and utilizing modern language models, we aim to improve predictive accuracy in this complex domain. This approach has been proven profitable after the first 5 weeks of the College Football season, and first 4 weeks of the NFL season.
