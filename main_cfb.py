import discord
import asyncio
import requests
import json
import time
import random
import anthropic
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np

with open("misc/anthropic_token.txt", "r") as f:
    anthropic_key = f.read().strip()

with open("misc/discord_token.txt", "r") as f:
    discord_token = f.read().strip()

with open("misc/perplexity_token.txt", "r") as f:
    perplexity_key = f.read().strip()

client = anthropic.Anthropic(
    # defaults to os.environ.get("ANTHROPIC_API_KEY")
    api_key = anthropic_key,
)

def comprehensive_perplexity_analysis(home, away, test=False):
    url = "https://api.perplexity.ai/chat/completions"
    print("Getting perplexity insight")

    def perplexity_query(messages):
        model_choices = ['large', 'huge']
        mod = random.choice(model_choices)
        model_choice = "llama-3.1-8b-instruct" if test else f"llama-3.1-sonar-{mod}-128k-online"
        payload = {
            "model": model_choice,
            "messages": messages
        }
        headers = {
            "Authorization": f"Bearer {perplexity_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        print(response)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"Error: {response}")
            return ""

    context = f"""
    You are a top college football analyst with decades of experience. You have comprehensive knowledge of {home} and {away}'s current rosters, playing styles, strengths, and weaknesses, as well as deep understanding of college football tactics, strategies, and trends. Provide an expert, impartial analysis based on this context. Cover both teams equally and avoid showing favoritism. Don't add anything about predictions or betting advice. Strive for true objectivity.
    """

    main_query = f"""
    Provide a comprehensive analysis of the upcoming {away} at {home} game, covering the following aspects:

1. Recent Performance and Trends:
   - Examine the most recent 3-4 games for both teams
   - Provide the current AP ranking for both teams
   - Discuss each teams' strength of schedule to date
   - Identify recent roster changes, if any
   - Identify significant trends in offensive or defensive performance
   - Highlight notable individual player performances
   - Discuss how these recent performances might impact the upcoming game
   - Highlight how each team has performed against the spread in recent games

2. Coaching Strategies and Adjustments:
   - Examine the coaching philosophies of {away}'s Coach] and {home}'s Coach]
   - Describe their typical offensive and defensive strategies
   - Analyze how they've adjusted their approaches in recent games
   - Predict potential in-game adjustments based on the opposing team's strengths and weaknesses

3. Key Player Matchups:
   - Identify 3-4 critical player matchups that could significantly influence the game outcome
   - Compare relevant statistics for each player in these matchups
   - Discuss how these matchups might affect overall team strategy
   - Predict which players are most likely to have standout performances

4. Environmental and Contextual Factors:
   - Analyze expected weather conditions for game day and their potential impact
   - Discuss any significant injuries/suspensions or returns from injury/suspensions for key players
   - Consider travel considerations, especially for the away team
   - Discuss home field advantage and its potential impact on the game.
   - Examine any notable off-field events or distractions affecting either team

5. Historical Performance in Similar Situations:
   - Analyze how each team has performed as favorite/underdog in the past two seasons
   - Examine each team's home/away record as relevant to this matchup
   - Discuss how each team has fared in conference/non-conference games as applicable
   - Evaluate each team's strength of schedule to date
   - Explore any relevant head-to-head history between the teams or coaches

6. Fan and Media Sentiment:
   - Summarize current fan expectations and concerns for each team
   - Highlight any media narratives or storylines surrounding the game
   - Discuss how public perception might influence team performance or betting lines

7. Special Teams and X-Factors:
   - Analyze the potential impact of special teams play
   - Identify any "X-factor" players who could unexpectedly influence the game
   - Discuss any unique tactical elements either team might employ

    Provide your analysis in a structured format, using headings for each main section and subsections where appropriate. Be concise but thorough, focusing on the most relevant and impactful information. 
    """

    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": main_query}
    ]

    full_analysis = ""
    while full_analysis == "":
        full_analysis = perplexity_query(messages)

    follow_up_query = f"""
    Based on your previous analysis of the {away} at {home} game, provide three specific, insightful follow-up questions that would offer deeper understanding of crucial aspects of this matchup. Then, answer these questions in detail.

    Format your response as follows:
    1. [Question 1]
    Answer: [Detailed answer to question 1]

    2. [Question 2]
    Answer: [Detailed answer to question 2]

    3. [Question 3]
    Answer: [Detailed answer to question 3]
    """

    messages.append({"role": "assistant", "content": full_analysis})
    messages.append({"role": "user", "content": follow_up_query})

    additional_insights = ""
    while additional_insights == "":
        additional_insights = perplexity_query(messages)

    return {
        "Main Analysis": full_analysis,
        "Additional Insights": additional_insights
    }

def scrape_game_stats(url):
    def convert_floats(obj):
        if isinstance(obj, dict):
            return {k: convert_floats(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_floats(v) for v in obj]
        elif isinstance(obj, str):
            try:
                float_value = float(obj)
                formatted = f"{float_value:.4f}"
                if formatted.endswith('.0000'):
                    return int(float_value)
                return formatted
            except ValueError:
                return obj
        else:
            return obj

    response = requests.get(url)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')
    # get var gameData json
    scripts = soup.find_all('script')
    game_data_script = None
    for script in scripts:
        if 'var gameData' in str(script):
            game_data_script = script
            break
    if game_data_script is None:
        return None
    game_data = str(game_data_script).split('var gameData = ')[1].split(';\n')[0]
    game_data = json.loads(game_data)
    home = game_data['gameInfo']['competitors'][0]['team']['displayName']
    away = game_data['gameInfo']['competitors'][1]['team']['displayName']
    game_data['matchup']['team'][0]['team'] = away
    game_data['matchup']['team'][1]['team'] = home

    game_data = convert_floats(game_data)
    return game_data['matchup']

def claude_game_analysis(game_data, home, away):
    initial_prompt = f"""YYou are a sports analyst tasked with creating a detailed preview for an upcoming college football game between {away} and {home}. Your goal is to analyze the provided data and generate an insightful preview of the game.

Here is the game data:
<game_data>
{game_data}
</game_data>

Follow these steps to create your preview:

1. Carefully analyze the provided data for both teams. Focus on their offensive and defensive statistics, rankings, and any standout metrics.

2. Identify the key strengths and weaknesses of each team based on their stats. Pay attention to metrics such as EPA (Expected Points Added) per play, success rates, yards per play, and rankings in various categories.

3. Compare the teams' offensive capabilities against each other's defensive capabilities. Look for potential mismatches or areas where one team might have a significant advantage.

4. Note any particularly impressive or concerning statistics, especially those where a team ranks very high or very low nationally.

5. Based on your analysis, create a detailed preview of the game. Your preview should include:
   - An overview of each team's offensive and defensive strengths
   - Potential key matchups or areas of advantage for each team
   - Any standout players or units based on the statistics
   - How each team's strengths might exploit the other's weaknesses
   - Any interesting statistical narratives that emerge from the data

6. Provide your preview in the following format:
   <preview>
   <'{home.replace(' ', '_')}_Analysis'>
   [Your analysis of {home} listed in the JSON data]
   <'/{home.replace(' ', '_')}_Analysis'>

   <'{away.replace(' ', '_')}_Analysis'>
   [Your analysis of {home} listed in the JSON data]
   <'/{away.replace(' ', '_')}_Analysis'>

   <matchup_overview>
   [Your overall analysis of how these teams match up, including key factors that could decide the game]
   </matchup_overview>
   </preview>

Remember to base your analysis solely on the provided statistical data. Do not reference any external information or make assumptions about players or coaches not reflected in the stats. Your preview should be detailed, insightful, and directly tied to the statistical information provided.

Use a professional and engaging tone in your writing. Avoid using clichés or overly technical language. Instead, explain complex statistics in a way that would be understandable to an average college football fan.

When referencing specific statistics, provide context by comparing them to national rankings or the opposing team's performance in the same category. This will help readers understand the significance of the numbers.

Finally, while your analysis should be data-driven, try to craft a compelling narrative about the game. Use the statistics to tell a story about how the game might unfold and what each team needs to do to secure a victory.

Begin your analysis now, following the format specified above."""

    print("Getting game analysis")
    # Replace placeholders like {{GAME_STATS}} with real values,
    # because the SDK does not support variables.
    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=3000,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": initial_prompt}
                ]
            }
        ]
    )

    initial_resp = str(message.content).replace("[TextBlock(text=", "").replace(", type='text')]", "")

    follow_up_prompt = f"""Based on your previous analysis of the {away} at {home} game, provide three specific, insightful follow-up questions that would offer deeper understanding of crucial aspects of this matchup. These questions should focus on deeper analysis of the game data, potential strategic implications, or exploring nuanced aspects of team matchups. Then, answer these questions in detail.

Format your response as follows:
1. [Question 1 focusing on a deeper aspect of team performance or strategy based on the provided data]
Answer: [Detailed answer to question 1, including how this aspect might influence the game]

2. [Question 2 addressing potential game-changing factors derived from the statistical analysis]
Answer: [Detailed answer to question 2, explaining the potential impact on the matchup]

3. [Question 3 exploring a nuanced aspect of the game data not fully covered in the initial analysis]
Answer: [Detailed answer to question 3, providing additional insights based on the statistical information]

In your answers, focus on information that can be derived from or is closely related to the game data provided. Emphasize how these factors could affect the teams' performance in this specific game based on the statistics, rankings, and other metrics provided.

Write your follow-up questions and answers inside <follow_up> tags."""
    print("following up")
    follow_up_message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=3000,
        temperature=0.0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": initial_prompt}
                ]
            },
            {
                "role": "assistant",
                "content": initial_resp
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": follow_up_prompt}
                ]
            }
        ]
    )

    follow_up_resp = str(follow_up_message.content).replace("[TextBlock(text=", "").replace(", type='text')]", "")

    return initial_resp + "\n\n" + follow_up_resp

def get_perplexity_odds(home, away):
    url = "https://api.perplexity.ai/chat/completions"

    prompt = f"""
    Task: Provide the current Moneyline, Spread, and Total lines for the {away} at {home} game in college football.
    
    Instructions:
    1. Use only the most recent and accurate odds from reputable sportsbooks, such as Fanduel, DraftKings, or ESPN.
    2. If odds are not available or you're unsure, use "N/A" for that field.
    3. Use whole numbers for spreads when possible (e.g., -3 instead of -3.0).
    4. Always include the team names in the spread fields.
    5. For totals, use decimal points if necessary (e.g., 45.5).
    6. Provide your response in the exact format shown below:

    [Current Odds] 
    Moneyline: 
    {away}: [AWAY_MONEYLINE_ODDS] 
    {home}: [HOME_MONEYLINE_ODDS] 

    Spread: 
    {away}: [AWAY_SPREAD] ([AWAY_SPREAD_ODDS]) 
    {home}: [HOME_SPREAD] ([HOME_SPREAD_ODDS]) 

    Total (Over/Under): 
    Over [TOTAL]: [OVER_ODDS] 
    Under [TOTAL]: [UNDER_ODDS]

    Return only the formatted response. Do not include any additional text, explanations, or context. If the odds for the Total (Over/Under) are unavailable, assume they are -110 each. If the odds for the Spread are unavailable, assume they are -110 each. If the Moneyline odds are unavailable, use "N/A" for both teams.
    """

    payload = {
        "model": "llama-3.1-sonar-huge-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are a precise AI assistant specializing in providing up-to-date sports betting odds for college football games. Always strive for accuracy and use 'N/A' if unsure."
            },
            {
                "role": "user",
                "content": prompt,
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {perplexity_key}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        result = response.json()
        odds_string = result['choices'][0]['message']['content']
        return odds_string
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None

def claude_expert_picks(insight_dict, home, away):
    quant_analysis = insight_dict["Quantitative Analysis"]
    main_qual_analysis = insight_dict["Qualitative Analysis"]
    game_odds = insight_dict["Game Odds"]

    prompt = f"""You are an advanced sports betting analyst tasked with providing value picks for an upcoming college football game between the {away} and the {home}.
    You will be given comprehensive game data and analysis in a structured format. Your job is to analyze this information, identify potential market inefficiencies, and provide picks for the Moneyline, Spread, and Total (Over/Under) bets.

The game data is divided into three main sections: Quantitative Analysis, Qualitative Analysis, and Game Odds. Here is the game data:

<game_data>
[Qualitative Analysis]
{main_qual_analysis}

[Quantitative Analysis]
{quant_analysis}

[Game Odds]
{game_odds}
</game_data>

Carefully analyze all the information provided in each section of the game data. Pay special attention to the Quantitative Analysis section, which contains crucial statistical data. Your primary goal is to identify potential inefficiencies in the betting market and find value picks.

When analyzing the data, focus on:

1. Qualitative Analysis:
- Recent performance and trends for both teams, both straight up and against the spread
- Each team's strength of schedule to date
- Coaching strategies and potential adjustments
- Key player matchups and standout performances
- Environmental and contextual factors (e.g., weather, injuries, travel considerations)
- Historical performance in similar situations
- Fan and media sentiment
- Special teams and potential X-factors

2. Quantitative Analysis:
- Team rankings in key statistical categories (e.g., total EPA, EPA per play, success rates)
- Offensive and defensive efficiency metrics
- Specific strengths and weaknesses for each team revealed by the data (e.g., passing vs. rushing performance)
- Comparative analysis of both teams' statistical profiles
- Consider how each team's strength of schedule might conflate these metrics

Note: Remember that basic statistical edges are likely already factored into the odds. Look for complex interactions or recent trends that might not be fully captured by widely available metrics.

3. Market Efficiency Considerations:
- Betting markets are extremely efficient and quickly incorporate most publicly available information.
- Be highly skeptical of any perceived edges. Most obvious advantages or disadvantages for either team are already reflected in the odds.
- Look for hidden value that might not be fully accounted for in the odds, such as:
  * Subtle changes in team dynamics or strategy that haven't received much media attention
  * Complex interactions between multiple factors that might be overlooked in simpler analyses
  * Potential overreactions or underreactions by the market to recent events
- Consider how sharp money (professional bettors) might be influencing the lines

Provide an equal amount of analysis supporting both the favorite and the underdog, as well as both the over and the under. Only after presenting both sides should you make your final recommendation. Strive for true objectivity in your analysis.

Begin by providing a brief summary of the key points across all sections, emphasizing the most significant quantitative findings, and your overall assessment of the game. Then, for each bet type (Moneyline, Spread, and Total), provide your analysis, pick (if any), and a detailed justification for your choice. Consider all relevant factors from the game data, ensuring you integrate both quantitative and qualitative insights.

When making your picks, keep the following principles in mind:
1. Market Efficiency: Assume that the betting markets are nearly perfect in their efficiency. Only suggest bets when you have identified a significant inefficiency that you are highly confident the market has overlooked or undervalued. 
2. Burden of Proof: The burden is on you to prove why your identified edge isn't already priced in. For every potential bet, explicitly state why you believe this particular insight or angle has been missed by the market.
3. Unit System: Rate each betting suggestion on a scale of 0 (no bet) to 5 (max bet) units. A rating of 0 means no bet is recommended, while a rating of 5 suggests a maximum bet within the bettor's predetermined unit system. Assume 1 unit is equal to 1% of the bettor's bankroll. Consider using the Kelly Criterion for optimal bet sizing.
4. Only suggest bets where you believe there is a clear edge based on the data provided. Avoid making bets based on gut feelings or subjective opinions.
5. Only bet on the Moneyline if the line is between -200 and +200. If the line is outside this range, consider betting on the spread instead.
6. Choose either to bet the Spread or the Moneyline, not both, based on which offers the better value proposition according to your analysis. If you choose to bet on moneyline, list "no bet" for the spread and vice versa.

Present your analysis and picks in the following JSON format:

{{"Summary" : [Provide a very brief summary of the key points across all sections, emphasizing the most significant quantitative and qualitative findings, and your overall assessment of the game. Highlight any significant factors that stand out from the comprehensive analysis.],
"Moneyline" : {{"Analysis" : {{"Summary" : [Provide your reasoning for the Moneyline analysis here. This should be a detailed explanation of your thought process, citing specific data points from both the quantitative and qualitative analysis. Reference specific sections of the analysis where relevant.], 
"Market Efficiency" : [Explain why you believe your identified edge isn't already priced into the odds. Discuss how your insight differs from or goes beyond the obvious factors that all bettors would consider. Justify why you think this particular inefficiency exists in an otherwise highly efficient market.],
"Pick" : [State your Moneyline pick here],
"Units" : [Provide a suggested bet size from 0 to 5 units, with justification]}},
"Spread" : {{"Analysis" : {{"Summary" : [Provide your reasoning for the Moneyline analysis here. This should be a detailed explanation of your thought process, citing specific data points from both the quantitative and qualitative analysis. Reference specific sections of the analysis where relevant.], 
"Market Efficiency" : [Explain why you believe your identified edge isn't already priced into the odds. Discuss how your insight differs from or goes beyond the obvious factors that all bettors would consider. Justify why you think this particular inefficiency exists in an otherwise highly efficient market.],
"Pick" : [State your Spread pick here],
"Units" : [Provide a suggested bet size from 0 to 5 units, with justification]}},
"Total" : {{"Analysis" : {{"Summary" : [Provide your reasoning for the Moneyline analysis here. This should be a detailed explanation of your thought process, citing specific data points from both the quantitative and qualitative analysis. Reference specific sections of the analysis where relevant.], 
"Market Efficiency" : [Explain why you believe your identified edge isn't already priced into the odds. Discuss how your insight differs from or goes beyond the obvious factors that all bettors would consider. Justify why you think this particular inefficiency exists in an otherwise highly efficient market.],
"Pick" : [State your Total pick here],
"Units" : [Provide a suggested bet size from 0 to 5 units, with justification]}}}}

Ensure that your reasoning is clear, logical, and well-supported by the provided game data. Your picks should reflect a careful consideration of all available information, with a focus on identifying and exploiting market inefficiencies. Be prepared to recommend "No Bet" if you don't find any significant edge in any market. Thoroughly justify any betting suggestion with clear reasoning on why the edge is significant enough to warrant a bet, and explain how you arrived at your unit rating.

If you find any areas where the analysis might be incomplete or where you have differing opinions based on your knowledge, please mention these in your summary or relevant betting analysis sections.

Remember, the goal is to make the most accurate and profitable picks based on the data provided, while being extremely mindful of market efficiency. It's entirely acceptable to recommend no bets if you can't identify any clear, significant edges that you're confident the market has missed or undervalued. Quality of analysis is far more important than quantity of bets suggested.
"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=3000,
        temperature=0.1,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt}
                ]
            }
        ]
    )

    resp = str(message.content).replace("[TextBlock(text=", "").replace(", type='text')]", "")
    return resp

def get_consensus_pick(expert_data, home, away):
    print("Getting consensus pick")
    consensus_prompt = f"""You are an elite college football betting analyst and synthesizer, tasked with critically evaluating multiple expert opinions to determine the most accurate and valuable betting recommendations for the game between the {home} and the {away}. Your goal is to leverage the collective wisdom of the experts while applying advanced analytical techniques to improve pick accuracy.
    
    You have been provided with analyses from several expert agents. Each expert has given their insights on the Moneyline, Spread, and Total markets for this game. Your task is to synthesize these opinions and provide a final recommendation for each market.
    
    Here is the expert data you need to analyze:
    <expert_data>
    {expert_data}
    </expert_data>
    
    For each betting market (Moneyline, Spread, and Total), please:
    
    1. Tally the experts' picks and determine the most common recommendation.
    2. If there's no clear consensus, choose "No Bet" as the recommendation.
    3. Summarize the most frequently mentioned factors that experts used to support their picks.
    4. Calculate the average unit rating based on the experts' recommendations, rounding to the nearest 0.5 unit. If the average is below 0.5, use 0 (No Bet).

    Important: Do not recommend bets on both the Moneyline and Spread. Choose the one that offers better value according to the expert opinions. If you choose to bet on the Moneyline, list "No Bet" for the Spread and vice versa.

    Present your analysis and official picks in the following JSON format:

    {{"analysis": {{"Moneyline" : {{"Summary": [Comprehensive summary of expert opinions, original data, and your critical analysis],
    "Key_Insights": [Most compelling arguments and data points from experts and original data],
    "Risk_Factors": [Discussion of potential risks or uncertainties],
}},
    "Spread" : {{"Summary": [Comprehensive summary of expert opinions, original data, and your critical analysis],
    "Key_Insights": [Most compelling arguments and data points from experts and original data],
    "Risk_Factors": [Discussion of potential risks or uncertainties],
}},
    "Total" : {{"Summary": [Comprehensive summary of expert opinions, original data, and your critical analysis],
    "Key_Insights": [Most compelling arguments and data points from experts and original data],
    "Risk_Factors": [Discussion of potential risks or uncertainties],
}},    
    "official_picks": {{"Moneyline": {{"Pick": [Your official Moneyline pick],
    "Reasoning": [Paragraph explanation of your reasoning],
    "Units": [0-5]}},
    "Spread": {{"Pick": [Your official Spread pick],
    "Reasoning": [Paragraph explanation of your reasoning],
    "Units": [0-5]}},
    "Total": {{"Pick": [Your official Total pick],
    "Reasoning": [Paragraph explanation of your reasoning],
    "Units": [0-5]}},
    "moneyline_vs_spread": {{"Preferred Bet": [Choose either Moneyline or Spread],
    "Justification": "[Explain why you believe this bet offers better value]"}}}}
    
Important considerations:
- Do not add any of your own analysis or insight. Your role is solely to aggregate and summarize the experts' opinions.
- If expert opinions are evenly split or too divergent, recommend "No Bet" for that market.
- In the "Reasoning" section, list only the factors mentioned by multiple experts. Do not include unique insights mentioned by only one expert.
- Ensure that the "Units" rating accurately reflects the average of the experts' recommendations.
- Remember to choose either Moneyline or Spread based on which offers better value according to expert opinions. Do not recommend both.

Your role is to represent the opinions of the expert panel, and to provide the most informed and well-reasoned betting recommendations possible, synthesizing the expertise of multiple college football experts.

Return only the JSON-formatted analysis without any additional text or context. Ensure it can be loaded into a JSON object without errors. 
"""

    # Replace {expert_data} in the prompt with the actual expert data
    consensus_prompt = consensus_prompt.replace("{expert_data}", expert_data)

    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=5000,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": consensus_prompt
                    }
                ]
            }
        ]
    )
    content = str(message.content)
    content = content.replace("[TextBlock(text='", "")
    content = content.replace("', type='text')]", "")
    content = content.strip()

    # Remove escaped newlines and replace with actual newlines
    content = content.replace('\\n', '\n')
    # Remove escaped quotes
    content = content.replace("\\'", "'")
    content = content.replace("  ", "")
    content = content.replace("\n", " ")
    return content

def get_consensus_pick_alt(expert_data, home, away):
    consensus_prompt = f"""You are a sports betting synthesizer tasked with aggregating multiple expert opinions to determine the most consensus betting recommendations for a given game. Your goal is to summarize the collective wisdom of the experts without adding your own analysis.

Here are the analyses from multiple expert agents:
 <expert_data>
{expert_data}
</expert_data>

 Each expert has given their insights and picks on the Moneyline, Spread, and Total markets for this game. Your task is to synthesize these opinions and provide a consensus recommendation for each market.
For each betting market (Moneyline, Spread, and Total), please:

1. Tally the experts' picks and determine the most common recommendation.
2. If there's no clear consensus, choose "No Bet" as the recommendation.
3. Summarize the most frequently mentioned factors that experts used to support their picks.
4. Calculate the average unit rating based on the experts' recommendations, rounding to the nearest 0.5 unit. If the average is below 0.5, use 0 (No Bet).

Important: Do not recommend bets on both the Moneyline and Spread. Choose the one that offers better value according to the expert opinions. If you choose to bet on the Moneyline, list "No Bet" for the Spread and vice versa.

Present your analysis and official picks in the following JSON format:

{{"Expert_Analysis": {{"Moneyline" : {{"Summary": [Comprehensive summary of expert opinions],
"Key_Insights": [Most compelling arguments and data points from experts],
"Risk_Factors": [Discussion of potential risks or uncertainties from the experts],
}},
"Spread" : {{"Summary": [Comprehensive summary of expert opinions],
"Key_Insights": [Most compelling arguments and data points from experts],
"Risk_Factors": [Discussion of potential risks or uncertainties],
}},
"Total" : {{"Summary": [Comprehensive summary of expert opinions],
"Key_Insights": [Most compelling arguments and data points from experts],
"Risk_Factors": [Discussion of potential risks or uncertainties],
}},    
"official_picks": {{"Moneyline": {{"Pick": [The most common Moneyline pick among experts, or 'No Bet' if no consensus],
"Reasoning": [Paragraph including the most frequently mentioned factors supporting this pick],
"Units": [Average of expert unit ratings, rounded to nearest 0.5 (0-5 range), or 0 if 'No Bet']}},
"Spread": {{"Pick": [The most common Spread pick among experts, or 'No Bet' if no consensus],
"Reasoning": [Paragraph including the most frequently mentioned factors supporting this pick],
"Units": [Average of expert unit ratings, rounded to nearest 0.5 (0-5 range), or 0 if 'No Bet']}},
"Total": {{"Pick": [The most common Total (over/under) pick among experts, or 'No Bet' if no consensus],
"Reasoning": [Paragraph including the most frequently mentioned factors supporting this pick],
"Units": [Average of expert unit ratings, rounded to nearest 0.5 (0-5 range), or 0 if 'No Bet']}}}}
    
Important considerations:
- Do not add any of your own analysis or insight. Your role is solely to aggregate and summarize the experts' opinions.
- If expert opinions are evenly split or too divergent, recommend "No Bet" for that market.
- In the "Reasoning" section, list only the factors mentioned by multiple experts. Do not include unique insights mentioned by only one expert.
- Ensure that the "Units" rating accurately reflects the average of the experts' recommendations.
- Remember to choose either Moneyline or Spread based on which offers better value according to expert opinions. Do not recommend both. 
- Only recommend betting on the Moneyline if that team's odds are between -200 and +200. Otherwise, recommend the Spread.

Return only the JSON-formatted consensus picks without any additional text or context. Ensure it can be loaded into a JSON object without errors.

"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=5000,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": consensus_prompt
                    }
                ]
            }
        ]
    )
    content = str(message.content)
    content = content.replace("[TextBlock(text='", "")
    content = content.replace("', type='text')]", "")
    content = content.strip()

    # Remove escaped newlines and replace with actual newlines
    content = content.replace('\\n', '\n')
    # Remove escaped quotes
    content = content.replace("\\'", "'")
    content = content.replace("  ", "")
    content = content.replace("\n", " ")
    return content

def get_weekly_games(week):
    url = f'https://gameonpaper.com/cfb/year/2024/type/2/week/{week}?group=80'

    response = requests.get(url)
    html_content = response.text

    soup = BeautifulSoup(html_content, 'html.parser')
    matchups = []

    game_divs = soup.find_all('div', class_=['row', 'border', 'rounded', 'm-2', 'mb-4', 'spice-level-none'])
    for game_div in game_divs:
        try:
            game_date = game_div.find('span', class_='game-date').text
            teams = game_div.find_all('div', class_='d-flex me-auto')

            if len(teams) == 2:
                away_team = teams[0]
                home_team = teams[1]

                away_name = away_team.find('span', class_='h4').text.strip()
                home_name = home_team.find('span', class_='h4').text.strip()

                away_conf_span = away_team.find('span', class_='small text-muted h6')
                home_conf_span = home_team.find('span', class_='small text-muted h6')

                away_conf = away_conf_span.text.split(',')[-1].strip() if away_conf_span else "N/A"
                home_conf = home_conf_span.text.split(',')[-1].strip() if home_conf_span else "N/A"

                home_rank_span = home_team.find('span', class_='small text-muted me-1')
                home_rank = home_rank_span.text if home_rank_span else "Unranked"

                away_rank_span = away_team.find('span', class_='small text-muted me-1')
                away_rank = away_rank_span.text if away_rank_span else "Unranked"

                href = game_div.find('a', class_='btn btn-sm btn-outline-primary')['href']

                matchups.append({
                    'game_datetime': game_date,
                    'away_team': away_name,
                    'home_team': home_name,
                    'away_conference': away_conf,
                    'home_conference': home_conf,
                    'away_rank': away_rank,
                    'home_rank' : home_rank,
                    'href': href
                })
        except Exception as e:
            pass

    df = pd.DataFrame(matchups)

    if not df.empty:
        # Convert game_datetime to proper datetime object
        df['game_datetime'] = pd.to_datetime(df['game_datetime'], format='%Y-%m-%dT%H:%M%z')
        df['game_datetime'] = pd.to_datetime(df['game_datetime']) - pd.Timedelta(hours=4)

        # Sort the DataFrame by game_datetime
        df = df.sort_values('game_datetime')

    df['away_conference'].unique()

    p5 = ['Big 12', 'ACC', 'SEC', 'B1G', 'Pac-12']
    go5 = ['AAC', 'MWC', 'MAC', 'Sun Belt', 'C-USA']
    other = ['Independent']

    df['saturday'] = df['game_datetime'].dt.weekday == 5
    # for home and away conference, only keep everything after the first space
    df['away_conference'] = df['away_conference'].str.split(' ').str[1:].apply(lambda x: ' '.join(x))
    df['home_conference'] = df['home_conference'].str.split(' ').str[1:].apply(lambda x: ' '.join(x))

    def filter_games(row):
        both_ranked = row['away_rank'] != "Unranked" and row['home_rank'] != "Unranked"

        if row['saturday']:
            return both_ranked or (row['away_conference'] in p5 and row['home_conference'] in p5) or \
                ((row['away_team'] == 'ND' and (row['home_conference'] in p5 or row['home_rank'] != 'Unranked')) or
                 (row['home_team'] == 'ND' and (row['away_conference'] in p5 or row['away_rank'] != 'Unranked')))
        else:
            return both_ranked or ((row['away_conference'] in p5 + go5 + other) and \
                (row['home_conference'] in p5 + go5 + other))


    df = df[df.apply(filter_games, axis=1)]
    df['away_team'] = np.where(df['away_team'] == 'uga', "UGA", df['away_team'])
    df['home_team'] = np.where(df['home_team'] == 'uga', "UGA", df['home_team'])
    df = df.drop(columns = ['away_conference', 'home_conference'])
    df['href'] = 'https://gameonpaper.com' + df['href']
    df['game_datetime'] = df['game_datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    # convert datetime from utc to eastern
    return df

def format_for_discord(consensus_pick, home, away, gametime):
    prompt = f"""
    You are tasked with converting sports prediction data into a concise, engaging, and authoritative message for a Discord channel. The data contains analysis and official picks for various betting options in an upcoming college football game. This information comes from an ensemble of highly sophisticated, cutting-edge AI agents who were given data on advanced stats and qualitative factors influencing the game.
    Here is the prediction data to process:
<prediction_data>
{consensus_pick}
</prediction_data>

The game is set to kick off at {gametime}. 

Follow these steps to create the Discord message:

1. Start with a header that includes the team names, using alarm emojis (🚨) on either side. For example: 🚨{home} vs {away}🚨.
2. Directly below the header, include the scheduled kickoff time. Example: "🕒{gametime}".

2. For each betting option (Moneyline, Spread, Total):
   a. Use an appropriate emoji (💰 for Moneyline, 🏈 for Spread, 🔢 for Total).
   b. State the official pick and units (if applicable).
   c. Provide a handful key points from the summary or reasoning, using bullet points (-). Focus on analytical depth rather than specific probabilities. Each point should clearly reinforce the bet.
   d. Where applicable, cite advanced analytics metrics (e.g., DVOA, EPA, Success Rate, YAC, etc.) to support each point, explaining how they specifically relate to the bet.

3. Include an "AI Expert Consensus" section (💡) with 3-4 detailed bullet points summarizing the overall AI panel opinions. Each point should:
   a. Directly support the bet(s) we chose to make.
   b. Highlight a specific aspect of the AI agent analysis used.
   c. Explain how this analysis directly led to or supports the betting recommendations.

4. Use emojis sparingly to enhance readability without cluttering the message.

Key Considerations:
- Ensure the message is easy to read at a glance, highlighting the most important information for each betting option. 
- Return only the formatted message without any additional text or context.
- Refer to the AI panel as "expert AI agents"
- Avoid mentioning specific probabilities or percentages for betting outcomes. Instead, use qualitative terms to express confidence levels (e.g., "strong conviction", "moderate confidence", "slight edge").
- When citing advanced analytics, briefly explain their significance if it's not immediately obvious. 
- Don't make any reference to "real-time" data. Assume all data is real-time.
- Don't add anything about betting responsibly - our users already know that. Focus solely on the analysis and recommendations.
- Make sure your response is under 2000 characters.

"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=5000,
        temperature=0.2,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt}
                ]
            }
        ]
    )

    resp = str(message.content).replace("[TextBlock(text=", "").replace(", type='text')]", "")
    resp = resp.replace('"', "")
    return resp

def send_to_discord(message):
    message = message.replace("\\n", "\n")

    loop = asyncio.get_event_loop()
    client = discord.Client(intents=discord.Intents.default())
    guild_name = 'Algorhythm Bets'
    channel_name = 'cfb-official-picks'
    # send to discord bot
    @client.event
    async def on_ready():
        guild = discord.utils.get(client.guilds, name=guild_name)
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        await channel.send(f"""{message}""")
        await client.close()
    loop.run_until_complete(client.start(discord_token))

def primary_pick_engine(url, gametime, n_agents=3, testing=False):
    ### 2. Scrape game stats
    game_data = scrape_game_stats(url)
    away = game_data['team'][0]['team']
    home = game_data['team'][1]['team']

    ### 3. Get analysis from Claude
    claude_game_analysis_response = ""
    while claude_game_analysis_response == "":
        try:
            claude_game_analysis_response = claude_game_analysis(game_data, home, away)
        except Exception as e:
            print(f"Error: {e}")

    ### 5. Get analysis from perplexity API
    qual_insight = comprehensive_perplexity_analysis(home, away, test=testing)

    # get odds from perplexity
    odds = get_perplexity_odds(home, away)
    insight_dict = {"Quantitative Analysis": claude_game_analysis_response,
                    "Qualitative Analysis": qual_insight,
                    "Game Odds": odds}

    # poll claude experts
    num_experts = n_agents if testing == False else 2
    expert_dict = {}
    i = 0
    while len(expert_dict) < num_experts:
        try:
            response = claude_expert_picks(insight_dict, home, away)
            print(f"{response}")
            expert_dict[f"Expert {i+1}"] = response
            i += 1
        except Exception as e:
            print(f"Error: {e}")

    ### 8. Get final analysis from Claude

    consensus_pick = ""
    while consensus_pick == "":
        try:
            consensus_pick = get_consensus_pick(str(expert_dict), home, away)
        except Exception as e:
            print(f"Error: {e}")
    consensus_pick = json.loads(consensus_pick)

    ### 9. Clean for discord
    print("Formatting for discord")
    disc = ""
    while disc == "":
        try:
            disc = format_for_discord(consensus_pick, home, away, gametime)
        except Exception as e:
            print(f"Error: {e}")

    print(disc)
    while len(disc) > 2000:
       print("Message too long, retrying")
       disc = format_for_discord(consensus_pick, home, away, gametime)
       print(disc)

    send_to_discord(disc)

    return game_data, claude_game_analysis_response, qual_insight, odds, expert_dict, consensus_pick, disc


def main(week = 6, today_only = True):
    ### 1. Get URL of game
    df = get_weekly_games(week)

    today = datetime.now().strftime("%Y-%m-%d")
    # only keep games that are today - note that df['game_datetime'] is in dt.strftime('%Y-%m-%d %H:%M:%S')
    if today_only:
        df = df[df['game_datetime'].str.contains(today)]
    df = df.reset_index().drop(columns = 'index')
    print(f"{df.shape[0]} games today")

    # check if picks folder exists. if so, check if game exists in csv. if so, drop game from dataframe. if csv does not exist, create it
    if os.path.exists(f'picks/cfb/week_{week}_picks.xlsx'):
        existing_games = pd.read_excel(f'picks/cfb/week_{week}_picks.xlsx')
        df = df[~df['home_team'].isin(existing_games['home_team'])]
    else:
        print('exists = False')
        existing_games = pd.DataFrame()
    print("Today's games:")
    print(df)

    for index, row in df.iterrows():
        gametime = pd.to_datetime(row['game_datetime']).strftime('%I:%M %p EST')
        # format as 12 hour time with PM, AM, etc

        print(f"{row['away_team']} at {row['home_team']} ({gametime})")


        game_df = pd.DataFrame([row], index=[index])
        url = row['href']
        game_data, clade_game_analysis_response, qual_insight, odds, expert_dict, consensus_pick, disc = primary_pick_engine(url, gametime,  n_agents=5, testing=False)
        ## add to dataframe
        game_df.loc[index, 'game_data'] = str(game_data)
        game_df.loc[index, 'claude_game_analysis'] = str(clade_game_analysis_response)
        game_df.loc[index, 'qual_insight'] = str(qual_insight)
        game_df.loc[index, 'odds'] = str(odds)
        game_df.loc[index, 'expert_dict'] = str(expert_dict)
        game_df.loc[index, 'consensus_pick'] = str(consensus_pick)
        game_df.loc[index, 'discord_message'] = str(disc)
        game_df.loc[index, 'ML_pick'] = str(consensus_pick['official_picks']['Moneyline']['Pick']) + " (" + str(consensus_pick['official_picks']['Moneyline']['Units']) + " units)"
        game_df.loc[index, 'Spread_pick'] = str(consensus_pick['official_picks']['Spread']['Pick']) + " (" + str(consensus_pick['official_picks']['Spread']['Units']) + " units)"
        game_df.loc[index, 'Total_pick'] = str(consensus_pick['official_picks']['Total']['Pick']) + " (" + str(consensus_pick['official_picks']['Total']['Units']) + " units)"
        existing_games = pd.concat([existing_games, game_df])
        existing_games.to_excel(f'picks/cfb/week_{week}_picks.xlsx', index = False)

if __name__ == '__main__':
    main(week=6)