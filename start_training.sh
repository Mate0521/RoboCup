#!/bin/bash
# RoboCup Agent - Training v1.0.0
# Requiere: rcssserver corriendo

export TRAINING=true
export TEAM="TrainingTeam"
export NUM_AGENTS=11
export MAX_EPISODES=1000

python src/main_training.py
