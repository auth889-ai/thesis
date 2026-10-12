//
// PoiParams: SUMO point-of-interest parameters read and written through Veins's TraCI connection (the loops' "wired backhaul"
// between a road-side unit and the Python traffic-management client). Part of the Veins loops of DhakaFlow Nexus (2026-10-12).
// Follows the pattern of Veins's TraCICommandInterface::Vehicle::setParameter / getParameter (Copyright (C) 2006-2011 Christoph
// Sommer <christoph.sommer@uibk.ac.at>); see third_party/SOURCES.md.
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

#include "veins/modules/mobility/traci/TraCIBuffer.h"
#include "veins/modules/mobility/traci/TraCIConnection.h"
#include "veins/modules/mobility/traci/TraCIConstants.h"
#include "veins/modules/mobility/traci/TraCIScenarioManager.h"

namespace loops {

inline std::string getPoiParameter(const std::string& poiId, const std::string& key)
{
    using namespace veins;
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    TraCIBuffer response = c->query(TraCIConstants::CMD_GET_POI_VARIABLE, TraCIBuffer() << static_cast<uint8_t>(TraCIConstants::VAR_PARAMETER) << poiId << static_cast<uint8_t>(TraCIConstants::TYPE_STRING) << key);
    uint8_t cmdLength; response >> cmdLength;
    if (cmdLength == 0) { int32_t cmdLengthExt; response >> cmdLengthExt; }
    uint8_t responseId; response >> responseId;
    uint8_t variable; response >> variable;
    std::string id; response >> id;
    uint8_t type; response >> type;
    std::string value; response >> value;
    return value;
}

inline void setPoiParameter(const std::string& poiId, const std::string& key, const std::string& value)
{
    using namespace veins;
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    static const int32_t nParameters = 2;
    c->query(TraCIConstants::CMD_SET_POI_VARIABLE, TraCIBuffer() << static_cast<uint8_t>(TraCIConstants::VAR_PARAMETER) << poiId << static_cast<uint8_t>(TraCIConstants::TYPE_COMPOUND) << nParameters
                                                                 << static_cast<uint8_t>(TraCIConstants::TYPE_STRING) << key << static_cast<uint8_t>(TraCIConstants::TYPE_STRING) << value);
}

} // namespace loops
