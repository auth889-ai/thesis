//
// AmbulanceLoopRSU11p (see AmbulanceLoopRSU11p.h for the licence: GPL-2.0-or-later, derived from Veins's TraCIDemoRSU11p).
// Every DENM frame this RSU's 802.11p NIC really decodes is counted and written to its traffic light's SUMO parameters
// "veins.rx" (count) and "veins.rx_t" (simulation time of the last reception); nothing is forwarded and no signal is changed here.
//
#include "AmbulanceLoopRSU11p.h"

#include <sstream>

#include "veins/modules/application/traci/TraCIDemo11pMessage_m.h"
#include "veins/modules/mobility/traci/TraCIBuffer.h"
#include "veins/modules/mobility/traci/TraCIConnection.h"
#include "veins/modules/mobility/traci/TraCIConstants.h"
#include "veins/modules/mobility/traci/TraCIScenarioManager.h"

using namespace veins;
using namespace omnetpp;

Define_Module(AmbulanceLoopRSU11p);

void AmbulanceLoopRSU11p::initialize(int stage)
{
    DemoBaseApplLayer::initialize(stage);
    if (stage == 0) {
        tlsId = par("tlsId").stdstringValue();
        active = par("active").boolValue();
        findHost()->getDisplayString().setTagArg("t", 0, ("RSU " + tlsId.substr(0, 18)).c_str());
    }
}

void AmbulanceLoopRSU11p::setTrafficLightParameter(const std::string& key, const std::string& value)
{
    // SUMO's trafficlight.setParameter: CMD_SET_TL_VARIABLE, VAR_PARAMETER, a compound of two strings (as Veins's Vehicle::setParameter)
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    static const int32_t nParameters = 2;
    c->query(TraCIConstants::CMD_SET_TL_VARIABLE, TraCIBuffer() << static_cast<uint8_t>(TraCIConstants::VAR_PARAMETER) << tlsId << static_cast<uint8_t>(TraCIConstants::TYPE_COMPOUND) << nParameters
                                                               << static_cast<uint8_t>(TraCIConstants::TYPE_STRING) << key << static_cast<uint8_t>(TraCIConstants::TYPE_STRING) << value);
    flagsWritten++;
}

void AmbulanceLoopRSU11p::onWSM(BaseFrame1609_4* frame)
{
    TraCIDemo11pMessage* wsm = check_and_cast<TraCIDemo11pMessage*>(frame);
    std::istringstream data(wsm->getDemoData());
    std::string tag; data >> tag;
    if (tag != "DENM") return;
    denmReceived++;
    findHost()->getDisplayString().setTagArg("t", 0, ("RSU " + tlsId.substr(0, 18) + ": DENM rx " + std::to_string(denmReceived)).c_str());
    findHost()->getDisplayString().setTagArg("i", 1, "green");
    if (!active || tlsId.empty()) return;
    std::ostringstream t; t << simTime().dbl();
    setTrafficLightParameter("veins.rx", std::to_string(denmReceived));
    setTrafficLightParameter("veins.rx_t", t.str());
}

void AmbulanceLoopRSU11p::finish()
{
    DemoBaseApplLayer::finish();
    recordScalar("denmReceived", denmReceived);
    recordScalar("flagsWritten", flagsWritten);
}
