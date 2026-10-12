//
// AmbulanceLoop11p: the ambulance's DENM-like alert over IEEE 802.11p and the receiving cars' make-way, for the Veins loops
// of DhakaFlow Nexus (2026-10-12). Derived from Veins's TraCIDemo11p (Copyright (C) 2006-2011 Christoph Sommer
// <christoph.sommer@uibk.ac.at>) and from research/veins_dhaka/src/AmbulanceAlert11p (ours); see third_party/SOURCES.md.
//
// SPDX-License-Identifier: GPL-2.0-or-later
//
// This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as
// published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
// This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
// You should have received a copy of the GNU General Public License along with this program; if not, see
// <https://www.gnu.org/licenses/>.
//
#pragma once
#include "veins/modules/application/ieee80211p/DemoBaseApplLayer.h"

class AmbulanceLoop11p : public veins::DemoBaseApplLayer {
public:
    void initialize(int stage) override;
    void finish() override;
    ~AmbulanceLoop11p() override;

protected:
    bool isAmbulance = false;
    bool makingWay = false;
    bool equipped = true;
    bool active = true;
    simtime_t departedAt = -1;
    long alertsSent = 0, alertsReceived = 0, madeWay = 0;
    omnetpp::cMessage* sendTimer = nullptr;
    omnetpp::cMessage* releaseTimer = nullptr;

    void onWSM(veins::BaseFrame1609_4* wsm) override;
    void handleSelfMsg(omnetpp::cMessage* msg) override;
    void setVehicleVariable(uint8_t variable, int32_t value);
    void setVehicleVariable(uint8_t variable, const std::string& value);
    int32_t edgeLaneNumber(const std::string& road);
};
