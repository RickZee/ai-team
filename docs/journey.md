# The project's background and ongoing story

## Why I created this project

My wife and I were talking about advancements of agentic systems and their use in large corporations or government organizations.

I decided to make a quick prototype for how such system would like like.

## Approach

I am using a combination of AI tools:

* SuperGrok for quick research, since I don't have any limits on tokens
* Claude Code to create in-depth architecture documents and plans
* Cursor for executing the plans and implementing the system

## Journey

### Feb 15

Raining Sunday morning, 11 AM, coffee and the original ideation :)

Created the initial plans and prompts. Opus 4.5 created very nicely designed build plan and initial prompts.

The problem was - I started running them in cursor only to realize that Claude didn't really do a good job:

![See missing prompts screenshot](feb-14-missing-prompts.png)

So now I have gaps in implementation and need to start from scratch.

Also there is way to run multiple agents in Cursor in parallel.

Sunday 6 PM (had to do a short Costco run): Phase 0, 1 and 2 prompts are all completed. It's great Monday is a federal holiday in the US, should be able to finish all prompts for the 6 phases Opus generated for us. Can't wait to actually start testing. Are we really going to be able to run this team using just the local models in Ollama??

Generated so far, within approximately 6 working hours:

```text
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                          64           1675           1756           6255
Markdown                        15            690              0           2599
YAML                             3             59             15            381
Bourne Shell                     1             26             21            231
JSON                             4              0              0             20
-------------------------------------------------------------------------------
SUM:                            87           2450           1792           9486
-------------------------------------------------------------------------------
```

### Feb 16

This is very cool! After 2 hours of work, we are into running integration tests, at the end of Phase 4.

Knowing how it usually is, I expect to be stuck at this phase for several days. We'll see...

And we crushed! The integration tests successfully created the team and started executing a full flow tests. My my Mac with 36GB of unified memory got completely unresponsive. Even the resource monitor wasn't showing anything useful except that Cursor was consuming 92GB of memory. Out of available 36. And after several short minutes the computer rebooted.

Alright, we are now back to the very typical back and forth with Cursor. It runs some tests, while skipping or disabling others. When it doesn't like a failed test, it just reports a success and asks you to move on.

## Feb 18

Skipping the busy Monday Feb 17... Who doesn't like to start learning at 5 AM?!

Yes, as expected, the default Cursor Composer is quite limited. It confuses setups, stops at integration tests where Sonnet 4.6 gives clear, short and precise instructions.

Cursor keeps bossing me around. I'm telling it to run the install script, then to execute the integration test. Result: it updated the readme file to tell *me* to execute the script and run the test. Thank you Cursor.

## Feb 21

After many out of memory reboots on my mac :)... Let's do something better. Let's use one of those LLM routers and see how much it'll cost.

## Feb 22

OK so running a smaller LLM definitely affects the team's performance. Big surprise. Alright so we're saving on cost running it locally be losing big time on actually being able to achieve results.

Pivoting to using APIs, with strict cost control and monitoring today.

Also, monitoring the CrewAI using logs is awkward. Let's build a very simple UI for it. Or TUI, as most people are not doing.

OK so the basic project is now working. Now testing every step, adding more guardrails and tweaking prompts.

Let's plan to deploy it on AWS AgentCore as well.

After multiple test runs using Ollama - it's now clear that not only it's slow, but also not feasible at the moment if you really want to make any progress. Most of the test runs are very slow, the local models are way to dumb to perform tasks, and the system crashes several times a day because I don't have enough memory.

Ok so for the next time - migrate from Ollama to OpenRouter and try running again.
