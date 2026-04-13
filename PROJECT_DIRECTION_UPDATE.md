# Project Direction Update

## Current direction

This project is changing direction.

The primary focus is now:

- **Cheat Engine**
- **x64dbg**
- **ReClass.NET**
- other stable, established third-party reverse-engineering tools

The main goal is to use those tools to identify, validate, and model memory structures related to RIFT orientation, camera data, transforms, and nearby object state.

## What is no longer the priority

We are **de-emphasizing ad hoc, on-the-fly scripts** created during exploration.

Reason:

- too much brittleness
- too many partial experiments
- too much maintenance cost
- too much noise in the repo
- lower confidence than mature third-party tooling

Exploratory scripts may still exist where they are genuinely useful, but they are no longer the center of the workflow.

## Practical workflow going forward

The preferred workflow is now:

1. use stable third-party tools to locate and inspect candidate memory structures
2. capture larger, better-labeled evidence sets
3. validate candidates through repeated tests
4. model likely structures with established tools
5. only after that, implement narrow, evidence-backed code in this repo if needed

## Repository implications

Going forward, the repo should favor:

- core reader code that still has a clear purpose
- minimal supporting utilities that are proven useful
- documentation of verified findings
- removal of obsolete, duplicate, or low-value experimental scripts

## Guiding principle

**Tool-assisted discovery first.  
Custom code second.  
Temporary script sprawl no longer drives the project.**
