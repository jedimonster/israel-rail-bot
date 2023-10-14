#!/usr/bin/env bash
set -ex

sudo service rail_bot stop
git -C railbot/israel-rail-bot pull
sudo service rail_bot start
sudo service rail_bot status
