#include "AmbulanceAlert11p.h"

#include <sstream>

#include "veins/modules/application/traci/TraCIDemo11pMessage_m.h"
#include "veins/modules/mobility/traci/TraCIBuffer.h"
#include "veins/modules/mobility/traci/TraCIConnection.h"
#include "veins/modules/mobility/traci/TraCIConstants.h"
#include "veins/modules/mobility/traci/TraCIScenarioManager.h"

using namespace veins;
using namespace omnetpp;

Define_Module(AmbulanceAlert11p);

static const int32_t RESCUE_LANE_CHANGE_MODE = 1605;   // as core/simulation/ambulance/makeway.py (SUMO's bluelight device)
static const int32_t DEFAULT_LANE_CHANGE_MODE = 1621;   // SUMO's default

AmbulanceAlert11p::~AmbulanceAlert11p()
{
    cancelAndDelete(sendTimer);
    cancelAndDelete(releaseTimer);
}

void AmbulanceAlert11p::initialize(int stage)
{
    DemoBaseApplLayer::initialize(stage);
    if (stage == 0) {
        sendTimer = new cMessage("ambulance alert");
        releaseTimer = new cMessage("make way: release");
    }
    else if (stage == 1) {
        isAmbulance = mobility->getExternalId() == par("ambulanceId").stdstringValue();
        equipped = isAmbulance || uniform(0, 1) < par("equippedShare").doubleValue();
        if (!equipped) findHost()->getDisplayString().setTagArg("i", 1, "gray");
        if (isAmbulance) {
            departedAt = simTime();
            if (par("guiColours").boolValue()) {                                   // display only: the ambulance green in both windows
                traciVehicle->setColor(TraCIColor(0, 190, 70, 255));
                findHost()->getDisplayString().setTagArg("i", 1, "green");
            }
            else findHost()->getDisplayString().setTagArg("i", 1, "blue");
            scheduleAt(simTime() + par("alertInterval"), sendTimer);
        }
    }
}

void AmbulanceAlert11p::setVehicleVariable(uint8_t variable, int32_t value)
{
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    c->query(TraCIConstants::CMD_SET_VEHICLE_VARIABLE, TraCIBuffer() << variable << mobility->getExternalId() << TraCIConstants::TYPE_INTEGER << value);
}

void AmbulanceAlert11p::setVehicleVariable(uint8_t variable, const std::string& value)
{
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    c->query(TraCIConstants::CMD_SET_VEHICLE_VARIABLE, TraCIBuffer() << variable << mobility->getExternalId() << TraCIConstants::TYPE_STRING << value);
}

void AmbulanceAlert11p::handleSelfMsg(cMessage* msg)
{
    if (msg == sendTimer) {
        Coord p = mobility->getPositionAt(simTime());
        TraCIDemo11pMessage* wsm = new TraCIDemo11pMessage("ambulance alert");
        populateWSM(wsm);
        std::ostringstream data;
        data << p.x << " " << p.y << " " << mobility->getRoadId();
        wsm->setDemoData(data.str().c_str());
        sendDown(wsm);
        alertsSent++;
        findHost()->getDisplayString().setTagArg("t", 0, ("alerts sent " + std::to_string(alertsSent)).c_str());
        scheduleAt(simTime() + par("alertInterval"), sendTimer);
    }
    else if (msg == releaseTimer) {
        makingWay = false;
        setVehicleVariable(TraCIConstants::VAR_LANECHANGE_MODE, DEFAULT_LANE_CHANGE_MODE);
        setVehicleVariable(TraCIConstants::VAR_LATALIGNMENT, std::string("center"));
        traciVehicle->setColor(TraCIColor(200, 200, 200, 255));
        findHost()->getDisplayString().setTagArg("i", 1, "");
    }
    else {
        DemoBaseApplLayer::handleSelfMsg(msg);
    }
}

void AmbulanceAlert11p::onWSM(BaseFrame1609_4* frame)
{
    if (isAmbulance || !equipped) return;
    TraCIDemo11pMessage* wsm = check_and_cast<TraCIDemo11pMessage*>(frame);
    alertsReceived++;
    std::istringstream data(wsm->getDemoData());
    double x, y;
    data >> x >> y;
    Coord me = mobility->getPositionAt(simTime());
    if (me.distance(Coord(x, y, me.z)) > par("makewayDistance").doubleValue()) return;
    if (!makingWay) {
        makingWay = true;
        madeWay++;
        setVehicleVariable(TraCIConstants::VAR_LANECHANGE_MODE, RESCUE_LANE_CHANGE_MODE);
        setVehicleVariable(TraCIConstants::VAR_LATALIGNMENT, std::string("right"));
        if (par("guiColours").boolValue()) {                                       // display only: alerted cars yellow
            traciVehicle->setColor(TraCIColor(255, 220, 0, 255));
            findHost()->getDisplayString().setTagArg("i", 1, "yellow");
        }
        else {
            traciVehicle->setColor(TraCIColor(255, 150, 0, 255));
            findHost()->getDisplayString().setTagArg("i", 1, "orange");
        }
    }
    cancelEvent(releaseTimer);
    scheduleAt(simTime() + par("makewayHold"), releaseTimer);
}

void AmbulanceAlert11p::handlePositionUpdate(cObject* obj)
{
    DemoBaseApplLayer::handlePositionUpdate(obj);
}

void AmbulanceAlert11p::finish()
{
    DemoBaseApplLayer::finish();
    recordScalar("alertsSent", alertsSent);
    recordScalar("alertsReceived", alertsReceived);
    recordScalar("madeWay", madeWay);
    if (isAmbulance) recordScalar("ambulanceTimeInNetwork", (simTime() - departedAt).dbl());
}
