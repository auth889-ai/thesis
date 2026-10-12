//
// AmbulanceLoopRSU11p: a road-side unit at a signalised junction that, on a REAL 802.11p reception of the ambulance's DENM, flags
// its traffic light for pre-emption through a SUMO parameter (the Python TraCI client applies the signal override). Part of the
// Veins loops of DhakaFlow Nexus (2026-10-12). Derived from Veins's TraCIDemoRSU11p (Copyright (C) 2006-2011 Christoph Sommer
// <christoph.sommer@uibk.ac.at>); see third_party/SOURCES.md.
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

class AmbulanceLoopRSU11p : public veins::DemoBaseApplLayer {
public:
    void initialize(int stage) override;
    void finish() override;

protected:
    std::string tlsId;
    bool active = true;
    long denmReceived = 0, flagsWritten = 0;
    void onWSM(veins::BaseFrame1609_4* wsm) override;
    void setTrafficLightParameter(const std::string& key, const std::string& value);
};
