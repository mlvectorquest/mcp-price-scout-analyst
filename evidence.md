# Evidence

## Test 1: Scraping the sites

Prompt: `scrape these sites: {'cloudrift': 'https://www.cloudrift.ai/inference', 'deepinfra': 'https://deepinfra.com/pricing', 'fireworks': 'https://fireworks.ai/pricing#serverless-pricing', 'groq': 'https://groq.com/pricing'}`

The log confirms `Scraped 4/4 websites successfully: ['cloudrift', 'deepinfra', 'fireworks', 'groq']`.

![Test 1: Scraping](Test_1_Scraping.png)

## Test 2: Questions about the scraped content

For these follow-up questions the agent checks the stored data first (the SQLite database via `read_query`, then the saved pages via `extract_scraped_info`) and does not call `scrape_websites` again.

### Question 1

`How much does cloudrift ai (https://www.cloudrift.ai/inference) charge for deepseek v3?`

The agent calls `read_query` and answers from the stored data. No re-scrape.

![Test 2: Question 1](Test_2_Question_1.png)

### Question 2

`How much does deepinfra (https://deepinfra.com/pricing) charge for deepseek v3`

The agent calls `read_query` and answers from the stored data. No re-scrape.

![Test 2: Question 2](Test_2_Question_2.png)

### Question 3

`How much does fireworks (https://fireworks.ai/pricing#serverless-pricing) charge for deepseek v3?`

The agent calls `read_query` first, finds no matching rows, then falls back to `extract_scraped_info` for the saved Fireworks page. No re-scrape. The log shows the saved page being truncated before it is sent to the model (`Truncating extract_scraped_info result from 208046 to 40000 characters for the model`).

![Test 2: Question 3](Test_2_Question_3.png)

## Test 3: Comparison and stored data

### Question 4: Comparison

`Compare cloudrift ai and deepinfra's costs for deepseek v3`

The agent calls `read_query`, finds pricing for both providers in the database, and gives a full natural-language comparison. No re-scrape.

![Test 3: Question 4](Test_3_Question_4.png)

### `show data`

Shows the 5 most recently stored pricing rows as a table: header row, separator row, one row per record with company, plan, input and output token pricing, and a closing separator.

![Test 3: show data](Test_3_show_data.png)
