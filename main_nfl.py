import re
from bs4 import BeautifulSoup

import json
from bs4 import BeautifulSoup
import pandas as pd
pd.set_option('display.max_colwidth', None)
import random
import requests
import time
import anthropic
import os
import discord
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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

def get_perplexity_odds(home, away):
    url = "https://api.perplexity.ai/chat/completions"

    prompt = f"""
    Task: Provide the current Moneyline, Spread, and Total lines for the {away} vs {home} NFL game.
    
    Instructions:
    1. Use only the most recent and accurate odds from reputable sportsbooks. Reference Action Network if needed.
    2. Use whole numbers for spreads when possible (e.g., -3 instead of -3.0).
    3. Always include the team names in the spread fields.
    4. For totals, use decimal points if necessary (e.g., 45.5).
    5. Provide your response in the exact format shown below:

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

    Return only the formatted response. Do not include any additional text, explanations, or context. If the odds for the Total (Over/Under) are unavailable, assume they are -110 each. If the odds for the Spread are unavailable, assume they are -110 each.
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

def parse_pff_data(greenline_data, lineups1_data, lineups2_data):
    def parse_table(soup, table_name):
        if table_name == "Team Metrics":
            table = soup.find('table', class_="m-matchup-table g-table g-table--compressed")
        elif table_name == "QB Comparison":
            table = soup.find_all('table', class_="m-matchup-table g-table g-table--compressed")[-1]
        else:
            table = soup.find('h3', string=table_name).find_parent('table')
        rows = table.find_all('tr')[1:]  # Skip header row
        data = {}
        for row in rows:
            cells = row.find_all(['th', 'td'])
            key = cells[0].text.strip().replace(' ', '_')
            away_value = cells[1].text.strip()
            home_value = cells[2].text.strip()
            data[key] = {away: away_value, home: home_value}

        if table_name == "Total":
            for key in data:
                data[key] = {"under": data[key][away], "over": data[key][home]}

        return data

    def parse_injuries(soup):
        try:
            injuries = {away: [], home: []}
            injury_tables = soup.find_all('table', class_='m-matchup-table g-table g-table--compressed')
            for i, table in enumerate(injury_tables[2:4]):  # Last two tables are injury tables
                team = away if i == 0 else home
                rows = table.find_all('tr')[1:]  # Skip header row
                for row in rows:
                    cells = row.find_all('td')
                    injury_data = {
                        "name": cells[0].text.strip(),
                        "position": cells[1].text.strip(),
                        "injury": cells[2].text.strip(),
                        "status": cells[3].text.strip(),
                        "grade": float(cells[4].find('div', class_='kyber-grade-badge__info-text').text.strip()),
                        "pos_war_rank": cells[5].text.strip()
                    }
                    injuries[team].append(injury_data)
        except Exception as e:
            injuries = None
        return injuries

    def parse_lineups(lineups, home, away, home_offense = True):

        def parse_depth_chart(html_content):
            soup = BeautifulSoup(html_content, 'html.parser')
            offense = {}
            defense = {}

            positions = soup.find_all('div', class_='depth-chart__position')
            for position in positions:
                position_key = position['data-position-key']
                position_title = position['title']
                players = position.find_all('div', class_='depth-chart__player')

                player_data = {
                    'title': position_title,
                    'players': [parse_player(player) for player in players]
                }

                if is_offensive_position(position_key):
                    offense[position_key] = player_data
                else:
                    defense[position_key] = player_data

            return {'offense': offense, 'defense': defense}

        def is_offensive_position(position):
            offensive_positions = ['QB', 'RB', 'FB', 'WR', 'TE', 'OL', 'C', 'G', 'T', 'LT', 'LG', 'RT', 'RG', 'HB']
            defensive_positions = ['DE', 'DT', 'LB', 'CB', 'S', 'DL', 'DB']

            if any(pos in position for pos in defensive_positions):
                return False
            elif any(pos in position for pos in offensive_positions):
                return True
            else:
                # If position is not clearly offensive or defensive, assume it's defensive
                return False

        def parse_player(player_div):
            jersey_number = player_div.find('span', class_='player-team-colors__number').text.strip().strip('#')
            name = player_div.find('span', class_='player-jersey__name').contents[0].strip()

            grade_div = player_div.find('div', class_='kyber-grade-badge__info-text')
            grade = grade_div.text.strip() if grade_div else None

            rank_p = player_div.find('p', class_='m-micro-copy')
            if rank_p:
                rank_text = rank_p.text.strip()
                rank_match = re.search(r'(\d+)(?:st|nd|rd|th)\s*/\s*(\d+)\s*(\w+)', rank_text)
                if rank_match:
                    rank, total, position = rank_match.groups()
                else:
                    rank, total, position = None, None, None
            else:
                rank, total, position = None, None, None

            return {
                'name': name,
                'grade': grade,
                'position_rank': rank,
                'overall_rank': total,
            }

        depth_chart = parse_depth_chart(lineups)
        # rename offense key
        if home_offense:
            depth_chart[home + '-offense'] = depth_chart.pop('offense')
            # rename defense key
            depth_chart[away + '-defense'] = depth_chart.pop('defense')
        else:
            depth_chart[away + '-offense'] = depth_chart.pop('offense')
            depth_chart[home + '-defense'] = depth_chart.pop('defense')

        return depth_chart

    soup = BeautifulSoup(greenline_data, 'html.parser')
    away = str(soup.find_all("span", class_="sr-only")[0].text)
    home = str(soup.find_all("span", class_="sr-only")[1].text)
    game_data = {
        "teams": {
            "away": away,
            "home": home
        },
        "spread": parse_table(soup, "Spread"),
        "moneyline": parse_table(soup, "Moneyline"),
        "total": parse_table(soup, "Total"),
        "impact_player_injuries": parse_injuries(soup),
        "game_metrics": parse_table(soup, "Team Metrics"),
        'qb_comparison': parse_table(soup, "QB Comparison")
    }
    # parse lineups
    lineups1_json = parse_lineups(lineups1_data, home, away, home_offense = True)
    lineups2_json = parse_lineups(lineups2_data, home, away, home_offense = False)
    # combine the two lineups
    lineups = {**lineups1_json, **lineups2_json}
    return game_data, lineups

def claude_adv_stats_analysis(adv_stats, home, away):
    print("Getting adv. stats analysis")
    initial_prompt = f"""YYou are a sports analyst tasked with creating a detailed preview for an upcoming college football game between {away} and {home}. Your goal is to analyze the provided data and generate an insightful preview of the game.

Here are the advanced stats:
<adv_stats>
{adv_stats}
</adv_stats>

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

When referencing specific statistics, provide context by comparing them to national rankings or the opposing team's performance in the same category. This will help readers understand the significance of the numbers.

Finally, while your analysis should be data-driven, try to craft a compelling narrative about the game. Use the statistics to tell a story about how the game might unfold and what each team needs to do to secure a victory.

Begin your analysis now, following the format specified above."""

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

def claude_game_analysis(game_data, home, away):
    initial_prompt = f"""You are a professional sports analyst tasked with creating an in-depth preview for an upcoming NFL game between the {away} and the {home}. You have been provided with comprehensive JSON data containing detailed statistics, betting information, and player grades for both teams. Your goal is to analyze this data and generate an insightful preview of the game.

Here are the game stats:
<game_stats>
{game_data}
</game_stats>

Follow these steps to create your preview:

1. Carefully analyze the provided data for both teams. Pay special attention to their offensive and defensive rankings, player grades, betting odds, and any standout metrics.

2. Identify the key strengths and weaknesses of each team based on the data. Consider factors such as power rankings, EPA (Expected Points Added) per play, quarterback performance, and player grades in various positions.

3. Compare the teams' offensive capabilities against each other's defensive capabilities. Look for potential mismatches or areas where one team might have a significant advantage.

4. Note any particularly impressive or concerning statistics, especially those where a team or player ranks very high or very low.

5. Analyze the betting information provided, including spread, moneyline, and total points. Consider how this information aligns with the statistical analysis.

6. Examine the impact player injuries and how they might affect the game.

7. Based on your analysis, create a detailed preview of the game. Your preview should include:
   - An overview of each team's offensive and defensive strengths
   - Potential key matchups or areas of advantage for each team
   - Analysis of quarterback performance and how it might impact the game
   - How each team's strengths might exploit the other's weaknesses
   - Any interesting statistical narratives that emerge from the data
   - Brief mention of how the betting odds align with your analysis

8. Provide your preview in the following format:
   <preview>
   <away_analysis>
   [Your analysis of {away}]
   </away_analysis>

   <home_analysis>
   [Your analysis of {home}]
   </home_analysis>

   <matchup_overview>
   [Your overall analysis of how these teams match up, including key factors that could decide the game]
   </matchup_overview>

   <betting_insights>
   [Brief analysis of the betting odds and how they relate to your statistical breakdown]
   </betting_insights>
   </preview>

Remember to base your analysis solely on the provided statistical data. Do not reference any external information or make assumptions about players or coaches not reflected in the stats. Your preview should be detailed, insightful, and directly tied to the statistical information provided."""

    print("Getting game analysis")
    # Replace placeholders like {{GAME_STATS}} with real values,
    # because the SDK does not support variables.
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
        temperature=0.2,
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

def claude_lineup_analysis(lineup_data):
    print("Getting lineup analysis")
    initial_prompt = f"""You are tasked with analyzing NFL starting lineup data to provide insights for game strategy and preparation. The data you will be working with is structured as follows:

<lineups_data>
{lineup_data}
</lineups_data>

This data contains information about the offensive and defensive lineups for two teams. Each player is listed with their position, grade, position rank, and overall rank.

To complete this task, follow these steps:

1. Analyze individual player performance:
   - Identify the top performers in each team based on their grades and ranks.
   - Note any players with exceptionally high or low grades.

2. Evaluate team strengths and weaknesses:
   - Compare the overall grades of offensive and defensive units for both teams.
   - Identify positions where each team excels or struggles.

3. Identify strategic implications:
   - Based on the strengths and weaknesses, determine potential strategies each team might employ.
   - Consider how each team's strengths might exploit the other team's weaknesses.

4. Find potential game-changing matchups:
   - Look for significant mismatches between opposing players or units.
   - Identify key players who could have a major impact on the game.

5. Use the data for game strategy and preparation:
   - Suggest offensive plays or defensive schemes that could be effective based on the lineup analysis.
   - Recommend areas where each team should focus their preparation efforts.

6. Prepare a comprehensive analysis report:
   - Summarize your findings for each of the above points.
   - Provide specific examples and data points to support your analysis.
   - Offer strategic recommendations for both teams based on your analysis.

Present your analysis in a clear, structured format. Use headings to separate different sections of your analysis. Include specific player grades, ranks, and positions when discussing individual performances or matchups. 

Focus only on the grades and ranks provided in the data.
Begin your analysis with an overview of the teams and the data provided, then proceed through each step of the analysis. Conclude with a summary of the key insights and strategic recommendations for both teams, based solely on the given data.
Write your complete analysis inside <analysis> tags."""
    initial_message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=5000,
        temperature=0.0,
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

    initial_resp = str(initial_message.content).replace("[TextBlock(text=", "").replace(", type='text')]", "")

    print("following up")
    follow_up_prompt = f"""Based on your previous analysis of the lineup data, provide three specific, insightful follow-up questions that would offer deeper understanding of crucial aspects of this matchup. These questions should focus on deeper analysis of the lineup data, potential strategic adjustments, or exploring nuanced aspects of player matchups. Then, answer these questions in detail.

Format your response as follows:
1. [Question 1 focusing on a deeper aspect of player matchups or team strategy]
Answer: [Detailed answer to question 1, including how this aspect might influence the game]

2. [Question 2 addressing potential strategic adjustments based on the lineup analysis]
Answer: [Detailed answer to question 2, explaining the potential impact on the matchup]

3. [Question 3 exploring a nuanced aspect of the lineup data not fully covered in the initial analysis]
Answer: [Detailed answer to question 3, providing additional insights based on the lineup data]

In your answers, focus on information that can be derived from or is closely related to the lineup data provided. Emphasize how these factors could affect the teams' performance in this specific game based on the players' grades, ranks, and positions.

Write your follow-up questions and answers inside <follow_up> tags."""

    follow_up_message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=3000,
        temperature=0.2,
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

def realtime_perplexity_analysis(home, away, test=False):
    url = "https://api.perplexity.ai/chat/completions"
    print("Getting real-time perplexity insight")

    def perplexity_query(messages):
        model_choices = ['small', 'large', 'huge']
        mod = random.choice(model_choices)
        model_choice = "llama-3.1-8b-instruct" if test else f"llama-3.1-sonar-{mod}-128k-online"
        time.sleep(10)

        payload = {
            "model": model_choice,
            "messages": messages
        }
        headers = {
            "Authorization": f"Bearer {perplexity_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"Error: {response}")
            return ""

    context = f"""
You are a top NFL analyst with decades of experience and access to real-time information. You have comprehensive knowledge of {home} and {away}'s current rosters, playing styles, strengths, and weaknesses, as well as deep understanding of NFL tactics, strategies, and trends. Your expertise also includes the ability to quickly gather and analyze the most recent developments affecting both teams. Provide an expert, impartial analysis based on the very latest information available. Focus on recent events, emerging trends, and real-time factors that could impact the upcoming game. Cover both teams equally and avoid showing favoritism. Don't add anything about predictions or betting advice. Strive for true objectivity and emphasize information that complements traditional statistical analysis.
    """

    main_query = f"""
Provide a real-time analysis for the upcoming NFL game between {away} and {home}, focusing on the following aspects:

1. Recent Performance and Trends:
   - Examine the most recent 3-4 games for both teams
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


    full_analysis = perplexity_query(messages)

    follow_up_query = f"""
Based on your previous analysis of the {away} at {home} game and considering the most recent developments, provide three specific, insightful follow-up questions that would offer deeper understanding of crucial aspects of this matchup. Focus on real-time factors, emerging trends, or recent events that could significantly impact the game. Then, answer these questions in detail, providing the most up-to-date information available.

Format your response as follows:
1. [Question 1 focusing on a real-time factor or recent development]
Answer: [Detailed answer to question 1, including how this factor might influence the game]

2. [Question 2 addressing an emerging trend or recent change in team dynamics]
Answer: [Detailed answer to question 2, explaining the potential impact on the matchup]

3. [Question 3 exploring a crucial aspect not covered in the initial analysis]
Answer: [Detailed answer to question 3, providing insights that complement the existing analysis]

In your answers, prioritize information that is not likely to be captured in traditional statistical analyses or historical data. Emphasize how these factors could affect the teams' performance in this specific game.
    """

    messages.append({"role": "assistant", "content": full_analysis})
    messages.append({"role": "user", "content": follow_up_query})

    additional_insights = perplexity_query(messages)

    return {
        "Main Analysis": full_analysis,
        "Additional Insights": additional_insights
    }


def scrape_adv_analytics(week, home, away):
    nfl_team_mapping = {
        "Cowboys": "DAL",
        "Saints": "NO",
        "Bengals": "CIN",
        "Rams": "LA",
        "Vikings": "MIN",
        "Jaguars": "JAX",
        "Steelers": "PIT",
        "Broncos": "DEN",
        "Eagles": "PHI",
        "Commanders": "WAS",
        "Patriots": "NE",
        "Chiefs": "KC",
        "Browns": "CLE",
        "Bills": "BUF",
        "Titans": "TEN",
        "Seahawks": "SEA",
        "Giants": "NYG",
        "Falcons": "ATL",
        "Panthers": "CAR",
        "Bears": "CHI",
        "Packers": "GB",
        "Texans": "HOU",
        "Colts": "IND",
        "Jets": "NYJ",
        "Buccaneers": "TB",
        "Cardinals": "ARI",
        "49ers": "SF",
        "Chargers": "LAC",
        "Raiders": "LV",
        "Ravens": "BAL",
        "Dolphins": "MIA",
        "Lions": "DET"
    }

    home = nfl_team_mapping[home]
    away = nfl_team_mapping[away]
    print(home)
    print(away)
    week = week.zfill(2)
    url= f'https://sumersports.com/games/2024-{week}-{away}-{home}/'
    def get_random_user_agent():
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/91.0.4472.80 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 11; SM-G991U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
            "Mozilla/5.0 (Android 11; Mobile; rv:68.0) Gecko/68.0 Firefox/88.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0",
        ]
        return random.choice(user_agents)

    chrome_options = Options()
    chrome_options.add_argument(f"user-agent={get_random_user_agent()}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": get_random_user_agent()})
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    driver.get(url)
    content = driver.page_source
    driver.quit()

    soup = BeautifulSoup(content, 'html.parser')
    stat_tables = soup.find_all('div', class_='stat-table')
    off_v_def = soup.find('div', class_='game-comparison-off-vs-def')
    def_v_off = soup.find('div', class_='game-comparison-def-vs-off')

    away_team = (soup.find_all('h2')[2].text).replace(' Statistics', '')
    home_team = (soup.find_all('h2')[-1].text).replace(' Statistics', '')

    away_stats = stat_tables[0:7]
    home_stats = stat_tables[7:]

    def parse_stat_tables(stats, team):
        result = {"Team Stats": "Team Stats", team: []}
        for table_html in stats:
            table_soup = BeautifulSoup(str(table_html), 'html.parser')
            table_dict = {}
            for div in table_soup.find_all('div', class_=['stat-total', 'stat-offense', 'stat-defense']):
                label = div.find('div', class_='label').text
                value = div.find('div', class_='value').text
                rank = div.find('div', class_='rank').text
                rank = int(rank.strip('th').strip('st').strip('nd').strip('rd'))
                table_dict[label] = {'value': value, 'rank': rank}
            result[team].append(table_dict)
        return result

    def parse_game_comparison(html_content, home_team, away_team, table_type):
        title = html_content.find('h2').text
        if table_type == 'off_v_def':
            title = title.replace('Offense', away_team + ' Offense').replace('Defense', home_team + ' Defense')
        elif table_type == 'def_v_off':
            title = title.replace('Offense', home_team + ' Offense').replace('Defense', away_team + ' Defense')

        result = {"title": title, "comparisons": []}
        comparison_soup = BeautifulSoup(str(html_content), 'html.parser')
        rows = comparison_soup.find_all('div', class_='game-table-row')

        for row in rows:
            cells = row.find_all('div', class_='game-table-cell')
            comparison = {
                'stat': cells[2].text,
                away_team + (" Offense" if table_type == 'off_v_def' else ' Defense'): {
                    'rank': cells[0].text.strip('th').strip('st').strip('nd').strip('rd'),
                    'value': cells[1].text
                },
                home_team + (" Defense" if table_type == 'off_v_def' else ' Offense'): {
                    'rank': cells[4].text.strip('th').strip('st').strip('nd').strip('rd'),
                    'value': cells[3].text
                }
            }
            result['comparisons'].append(comparison)

        return result

    home_stats_json = parse_stat_tables(home_stats, home_team)
    away_stats_json = parse_stat_tables(away_stats, away_team)
    team_stats = {'title': "Advanced Analytics", home_team: home_stats_json[home_team], away_team: away_stats_json[away_team]}

    off_v_def_comparison = parse_game_comparison(off_v_def, home_team, away_team, 'off_v_def')
    def_v_off_comparison = parse_game_comparison(def_v_off, home_team, away_team, 'def_v_off')

    combined_stats = {
        "team_stats": team_stats,
        "comparisons": {
            "offense_vs_defense": off_v_def_comparison,
            "defense_vs_offense": def_v_off_comparison
        }
    }

    return combined_stats

def claude_expert_picks(insight_dict, home, away):
    adv_stats_analysis = insight_dict["Adv. Stats Analysis"]
    game_analysis = insight_dict["Game Analysis"]
    lineup_analysis = insight_dict["Starting Lineup Analysis"]
    perplexity_analysis = insight_dict["Perplexity Analysis"]
    game_odds = insight_dict["Game Odds"]

    prompt = f"""
You are an advanced sports betting analyst tasked with providing value picks for an upcoming NFL game. You will be given comprehensive game data and analysis in a structured format. Your job is to analyze this information, identify potential market inefficiencies, and provide picks for the Moneyline, Spread, and Total (Over/Under) bets.

The game data is divided into five main sections: Game Analysis, Advanced Stats Analysis, Starting Lineup Analysis, Perplexity Analysis, and Game Odds. Review each section carefully to form your own expectations for the game outcome and potential betting lines. Here is the game data:
<game_data>
[Game Analysis]
{game_analysis}

[Advanced Stats Analysis]
{adv_stats_analysis}

[Starting Lineup Analysis]
{lineup_analysis}

[Perplexity Analysis]
{perplexity_analysis}

[Game Odds]
{game_odds}
</game_data>

Carefully analyze all the information provided in each section of the game data, including team comparisons, player matchups, coaching strategies, contextual factors, and current odds. Your primary goal is to identify potential inefficiencies in the betting market and find value picks.

Pay special attention to:
1. Recent team performance and head-to-head history
2. Key player matchups, especially quarterbacks
3. The impact of any new additions or significant lineup changes
4. Changes in defensive and offensive strategies
5. The influence of the stadium and home-field advantage
6. Current betting trends and public sentiment
7. Weather conditions, if applicable
8. Injuries or last-minute player updates

Note: Remember that basic statistical edges are likely already factored into the odds. Look for complex interactions or recent trends that might not be fully captured by widely available metrics.

Also pay attention to market efficiency considerations:
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

def claude_consensus_pick(expert_data, home, away):
    print("Getting consensus pick")
    consensus_prompt = f"""You are an elite NFL analyst and synthesizer, tasked with aggregating multiple expert opinions to determine the most consensus betting recommendations for the game between {home} and {away}. Your goal is to summarize the collective wisdom of the experts without adding your own analysis.

    Here is the expert data you need to analyze:
    <expert_data>
    {expert_data}
    </expert_data>

    You have been provided with analyses from multiple expert agents. Each expert has given their insights and picks on the Moneyline, Spread, and Total markets for this game. Your task is to synthesize these opinions and provide a consensus recommendation for each market.

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

Return only the JSON-formatted consensus picks without any additional text or context. Ensure it can be loaded into a JSON object without errors.
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

def format_for_discord(consensus_pick, home, away):
    prompt = f"""
    You are tasked with converting sports prediction data into a concise, engaging, and authoritative message for a Discord channel. The data contains analysis and official picks for various betting options in an upcoming NFL game. This information comes from an ensemble of highly sophisticated, cutting-edge AI agents who were given data on advanced stats and qualitative factors influencing the game.
    Here is the prediction data to process:
<prediction_data>
{consensus_pick}
</prediction_data>

Follow these steps to create the Discord message:

1. Start with a header that includes the team names, using football emojis (🏈) on either side. For example: 🏈{home} vs {away}🏈.

2. For each betting option (Moneyline, Spread, Total):
   a. Use an appropriate emoji (💰 for Moneyline, 🏈 for Spread, 🔢 for Total).
   b. State the official pick and units (if applicable).
   c. Provide a handful key points from the summary or reasoning, using bullet points (-). Focus on analytical depth rather than specific probabilities. Each point should clearly reinforce the bet.
   d. Where applicable, cite advanced analytics metrics (e.g., DVOA, EPA, Success Rate, YAC, etc.) to support each point, explaining how they specifically relate to the bet.

3. Add a "Key Factors" section (🔍) with 3-4 detailed bullet points. Each factor should explicitly connect to the betting recommendations, showing how it influences the AI agents' decisions. Include relevant advanced statistics that directly support these connections. Important: each point should clearly reinforce the bets we chose to make.

4. Include an "AI Expert Consensus" section (💡) with 3-4 detailed bullet points summarizing the overall AI panel opinions. Each point should:
   a. Directly support the bet(s) we chose to make.
   b. Highlight a specific aspect of the AI agent analysis used.
   c. Explain how this analysis directly led to or supports the betting recommendations.

5. Use emojis sparingly to enhance readability without cluttering the message.

Key Considerations:
- Ensure the message is easy to read at a glance, highlighting the most important information for each betting option. 
- Return only the formatted message without any additional text or context.
- Refer to the AI panel as "expert AI agents" and emphasize their advanced reasoning capabilities without using specific agent names or numbers.
- Avoid mentioning specific probabilities or percentages for betting outcomes. Instead, use qualitative terms to express confidence levels (e.g., "strong conviction", "moderate confidence", "slight edge").
- When citing advanced analytics, briefly explain their significance if it's not immediately obvious. 
- Don't make any reference to "real-time" data. Assume all data is real-time.
- Don't add anything about betting responsibly - our users already know that. Focus solely on the analysis and recommendations.
- Make sure your response is under 2000 characters.

"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
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
    channel_name = 'nfl-official-picks'
    # send to discord bot
    @client.event
    async def on_ready():
        guild = discord.utils.get(client.guilds, name=guild_name)
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        await channel.send(f"""{message}""")
        await client.close()
    loop.run_until_complete(client.start(discord_token))
    print("Message sent")

def primary_pick_engine(week, greenline, lineups1, lineups2):
    game_data, lineups = parse_pff_data(greenline, lineups1, lineups2)
    away = game_data['teams']['away']
    home = game_data['teams']['home']

    print('scraping advanced stats')
    adv_stats = None
    while adv_stats is None:
        try:
            adv_stats = scrape_adv_analytics(week, home, away)
        except:
            print('Error scraping advanced stats, retrying')
            time.sleep(5)

    claude_adv_stats = claude_adv_stats_analysis(adv_stats, home, away)

    claude_quant_insight = claude_game_analysis(game_data, home, away)

    lineup_analysis = claude_lineup_analysis(lineups)

    perplexity_analysis = realtime_perplexity_analysis(home, away)

    game_odds = get_perplexity_odds(home, away)

    insight_dict = {"Game Analysis": claude_quant_insight,
                    "Adv. Stats Analysis" : claude_adv_stats,
                    "Starting Lineup Analysis" : lineup_analysis,
                    "Perplexity Analysis": perplexity_analysis,
                    "Game Odds": game_odds}

    # poll Claude experts
    num_experts = 5
    expert_dict = {}
    for i in range(num_experts):
        print(f"Getting analysis from AI agent {i+1} of {num_experts}")
        response = claude_expert_picks(insight_dict, home, away)
        print(f"{response}")
        print('\n')
        expert_dict[f"Expert {i+1}"] = response

    ### 8. Get final analysis from Claude
    consensus_pick = claude_consensus_pick(str(expert_dict), home, away)
    consensus_pick = json.loads(consensus_pick)

    print("Formatting for discord")
    disc = format_for_discord(consensus_pick, home, away)
    print(disc)
    while len(disc) > 2000:
        print("Message too long, retrying")
        disc = format_for_discord(consensus_pick, home, away)
        print(disc)

    print("Sending to discord")
    send_to_discord(disc)
    return adv_stats, game_data, lineups, claude_adv_stats, claude_quant_insight, lineup_analysis, perplexity_analysis, game_odds, expert_dict, consensus_pick, disc

def main(week):
    week = str(week)
    df = pd.read_excel('nfl_schedule.xlsx', sheet_name = f"Week {week}")
    # get list of paths
    paths = df['Path'].tolist()
    # for each path, create it if it doesn't exist
    for path in paths:
        if not os.path.exists(f'nfl/week{week.lower().replace(" ", "")}/{path}'):
            os.makedirs(f'nfl/week{week.lower().replace(" ", "")}/{path}')
    df = df[df['Ignore'] != 1]
    if os.path.exists(f'picks/nfl/week_{week}_picks.xlsx'):
        existing_games = pd.read_excel(f'picks/nfl/week_{week}_picks.xlsx')
        df = df[~df['Home'].isin(existing_games['Home'])]
    else:
        print('exists = False')
        existing_games = pd.DataFrame()

    for index, row in df.iterrows():
        print(f"Processing {row['Away']} at {row['Home']}")
        game_df = pd.DataFrame([row], index=[index])

        path = row['Path']
        path = f'nfl/week{week.lower().replace(" ", "")}/{path}'

        with open(path+'/NFL Scores (1).html', 'r') as f:
            greenline = f.read()
        with open(path+'/NFL Scores (2).html', 'r') as f:
            lineups1 = f.read()
        with open(path+'/NFL Scores (3).html', 'r') as f:
            lineups2 = f.read()
        print(path)

        adv_stats, game_data, lineups, adv_stats_analysis, claude_quant_insight, lineup_analysis, perplexity_analysis, game_odds, expert_dict, consensus_pick, disc =  primary_pick_engine(week, greenline, lineups1, lineups2)

        ## add to dataframe
        game_df.loc[index, 'adv_stats'] = str(adv_stats)
        game_df.loc[index, 'adv_stats_analysis'] = str(adv_stats_analysis)
        game_df.loc[index, 'game_data'] = str(game_data)
        game_df.loc[index, 'lineups'] = str(lineups)
        game_df.loc[index, 'claude_quant_analysis'] = str(claude_quant_insight)
        game_df.loc[index, 'lineup_analysis'] = str(lineup_analysis)
        game_df.loc[index, 'perplexity_analysis'] = str(perplexity_analysis)
        game_df.loc[index, 'odds'] = str(game_odds)
        game_df.loc[index, 'expert_dict'] = str(expert_dict)
        game_df.loc[index, 'consensus_pick'] = str(consensus_pick)
        game_df.loc[index, 'discord_message'] = str(disc)
        game_df.loc[index, 'ML_pick'] = str(consensus_pick['official_picks']['Moneyline']['Pick']) + " (" + str(consensus_pick['official_picks']['Moneyline']['Units']) + " units)"
        game_df.loc[index, 'Spread_pick'] = str(consensus_pick['official_picks']['Spread']['Pick']) + " (" + str(consensus_pick['official_picks']['Spread']['Units']) + " units)"
        game_df.loc[index, 'Total_pick'] = str(consensus_pick['official_picks']['Total']['Pick']) + " (" + str(consensus_pick['official_picks']['Total']['Units']) + " units)"
        existing_games = pd.concat([existing_games, game_df])
        existing_games.to_excel(f'picks/nfl/week_{week}_picks.xlsx', index = False)


if __name__ == "__main__":
    main(week=5)


