//
// RoutingCar11p: a connected car of the forecast-routing loop in Veins (2026-10-12): sends its status over IEEE 802.11p every
// statusInterval, and changes route only when an advice frame addressed to it is really received. Derived from Veins's
// TraCIDemo11p (Copyright (C) 2006-2011 Christoph Sommer <christoph.sommer@uibk.ac.at>); see third_party/SOURCES.md.
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
#include <list>
#include <string>

#include "veins/modules/application/ieee80211p/DemoBaseApplLayer.h"

class RoutingCar11p : public veins::DemoBaseApplLayer {
public:
    void initialize(int stage) override;
    void finish() override;
    ~RoutingCar11p() override;

protected:
    bool active = true;
    long statusSent = 0, adviceReceived = 0, adviceApplied = 0, adviceInapplicable = 0, adviceDeferred = 0;
    omnetpp::cMessage* statusTimer = nullptr;
    omnetpp::cMessage* deferTimer = nullptr;
    std::string pendingMsgId;
    std::list<std::string> pendingRoute;
    int deferTries = 0;

    void onWSM(veins::BaseFrame1609_4* wsm) override;
    void handleSelfMsg(omnetpp::cMessage* msg) override;
    void applyAdvice();
    void logEntry(const std::string& outcome, const std::string& msgId, const std::string& road);
};
