# Smart DNS Companion with Reachy Mini

A goal-aware parental control system leveraging an NVIDIA Jetson Orin Nano, the Reachy Mini robot, and a local, AI-powered judge.

## Overview

Traditional parental controls are often simple, static blocking systems that create frustration rather than positive behavior change. This project reinvents that model.

We present a "Smart DNS Companion" that acts as a goal-setting and screen time management partner for children and adolescents. By routing network traffic through a custom DNS proxy on an NVIDIA Jetson Orin Nano, the system performs intelligent, goal-aware filtering of web content.

**What makes it special is the interactive feedback loop.** When a user attempts to access blocked content, they can speak directly to the **Reachy Mini robot companion** and present an argument for why unblocking is necessary (e.g., for research related to their goals). A local, TensorRT-optimized Large Language Model (LLM) judges the argument and dynamically updates the DNS whitelist based on the evaluation, with live parental notification.

This approach transforms parental control from a top-down restriction into a collaborative, goal-driven dialogue that teaches critical thinking and self-discipline.

## Architecture

The project is built on three core layers:

**1. Edge Compute Layer (NVIDIA Jetson Orin Nano):**
This is the central intelligence hub. It acts as the local network router and hosts the custom DNS handler.
* **DNS Resolver:** Goal-aware filtering of all DNS queries.
* **Goal Engine:** Builds dynamically updated allowlists and blocklists based on the user's defined goals and approved arguments.
* **LLM Judge:** A local, TensorRT-optimized LLM that performs fast edge inference to score and evaluate user arguments.
* **Screen Time Control:** Per-device scheduling and dynamic updates.
* **OpenClaw Agentic Tools & NVIDIA OSS models:** Power the agentic decision-making and interaction.

**2. Embodied Interface (Reachy Mini):**
The physical robot companion that makes goal setting and argument negotiation intuitive and friendly.
* **Goal Setting Dialogue:** Helps users define their daily productivity goals.
* **Argument Listener:** Listens to user spoken arguments when content is blocked.
* **Multimodal Feedback:** Provides a clear, friendly face and voice for communication.

**3. Parent Communication Layer (Agora SDK):**
Direct, real-time access for parents to provide input and intervention.
* **Parent Channel:** Enables parents to monitor activity.
* **Audio/Video Calls & Real-time Messaging:** Allows parents to directly step in and "lecture" or discuss tasks with the child via the robot or user devices.

### System Architecture Diagram

![System Architecture Diagram and Argue Your Case Workflow](image_5c4b63.png)
*Figure 1: High-level System Architecture Diagram and "Argue Your Case" Workflow.*

## The "Argue Your Case" Workflow

A unique and core feature of this system is the dynamic unblocking process. Rather than a simple 'denied' page, a blocked request triggers a unique collaborative flow.

1.  **Blocked (DNS denied):** A user attempts to access a restricted site.
2.  **User Argues (Speaks to Reachy):** The user presents their case to the robot companion, explaining how access is necessary for their declared goal.
3.  **LLM Judges (Scores argument):** The local LLM judge evaluates the spoken argument for merit.
4.  **Granted / Denied (DNS updated live):** If the argument is strong, the DNS whitelist is instantly updated, and access is granted. The status is communicated back to the user.
5.  **Parent Notified (via Agora):** The entire process, including the user's argument and the LLM's decision, is communicated to the parent via the Agora-powered channel.

## Key Features

* **Custom Goal-Aware DNS Handling:** All web access is filtered to align with daily goals.
* **Dynamic, AI-Powered Unblocking:** Users can actively challenge blocks through logical arguments.
* **Private and Secure (Local-First):** The DNS server, LLM, and interaction models all run at the edge on the Orin Nano, keeping usage and voice data private.
* **Robot Companion Interface:** Uses the Reachy Mini for friendly, embodied interaction and dialogue.
* **Flexible Screen Time Management:** Complete screen time control and dynamic scheduling.
* **Integrated Parent-to-Child Communication:** Agora-powered real-time audio, video, and messaging.
* **Study Time Tracking:** The robot tracks actual study hours.
* **Multilingual Support:** Starting with Chinese to target a larger user base.

## Vision

This system aims to create a more holistic and supportive environment for developing self-discipline and goal-setting skills. The nuanced, AI-mediated dialogue helps users understand the value of their time, while direct parental communication provides necessary oversight and guidance. This represents a new standard for localized, private, and interactive parental control.