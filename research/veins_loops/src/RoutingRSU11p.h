//
// RoutingRSU11p: a road-side unit of the forecast-routing loop in Veins (2026-10-12): every status frame it really receives is
// written to its SUMO point of interest (the wired backhaul to the Python traffic-management client), and every advice the
// client leaves on that point of interest is broadcast over IEEE 802.11p. Derived from Veins's TraCIDemoRSU11p (Copyright (C)
// 2006-2011 Christoph Sommer <christoph.sommer@uibk.ac.at>); see third_party/SOURCES.md.
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
#include <string>

#include "veins/modules/application/ieee80211p/DemoBaseApplLayer.h"

class RoutingRSU11p : public veins::DemoBaseApplLayer {
public:
    void initialize(int stage) override;
    void finish() override;
    ~RoutingRSU11p() override;

protected:
    std::string poiId;
    bool active = true;
    long statusReceived = 0, adviceSent = 0;
    std::string pending;                 // statuses received since the last flush
    std::string lastSeq;
    omnetpp::cMessage* tick = nullptr;

    void onWSM(veins::BaseFrame1609_4* wsm) override;
    void handleSelfMsg(omnetpp::cMessage* msg) override;
};
