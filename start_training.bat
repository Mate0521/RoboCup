@echo off
title RoboCup Training - PPO v2
echo ============================================
echo  RoboCup Agent - Training v1.0.0
echo ============================================
echo.
echo Asegurate de que rcssserver este corriendo:
echo   rcssserver server::auto_mode=true server::synch_mode=false
echo.
echo Si el servidor esta en otro host, usa:
echo   set SERVER_IP=192.168.x.x
echo.
echo ============================================
echo.

set TRAINING=true
set TEAM=TrainingTeam
set NUM_AGENTS=11
set MAX_EPISODES=1000

python src\main_training.py

pause
