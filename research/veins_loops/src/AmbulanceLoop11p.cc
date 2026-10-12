//
// AmbulanceLoop11p (see AmbulanceLoop11p.h for the licence: GPL-2.0-or-later, derived from Veins's TraCIDemo11p and our
// AmbulanceAlert11p). The ambulance broadcasts a DENM-like WSM every alertInterval ("DENM x y road lanePosition nextRoad..."), its
// position, road and the next roads of its route, and writes its count of alerts into its SUMO parameter "veins.tx" so the
// Python client can show it. A car that really receives the frame applies make-way rule v2 (core/simulation/ambulance/makeway.py:
// lane-change mode 1605, lateral alignment left on the highest lane and right elsewhere, its own route lane changes kept) when it
// is on the ambulance's road ahead of it or on one of the next roads, within makewayDistance; it gets its settings back after
// makewayHold. Qtenv/sumo-gui colours: the ambulance red, a car that made way green, a car without a radio grey.
//
#include "AmbulanceLoop11p.h"

#include <sstream>
#include <vector>

#include "veins/modules/application/traci/TraCIDemo11pMessage_m.h"
#include "veins/modules/mobility/traci/TraCIBuffer.h"
#include "veins/modules/mobility/traci/TraCIConnection.h"
#include "veins/modules/mobility/traci/TraCIConstants.h"
#include "veins/modules/mobility/traci/TraCIScenarioManager.h"

using namespace veins;
using namespace omnetpp;

Define_Module(AmbulanceLoop11p);

static const int32_t RESCUE_LANE_CHANGE_MODE = 1605;   // as core/simulation/ambulance/makeway.py (SUMO's bluelight device)
static const int32_t DEFAULT_LANE_CHANGE_MODE = 1621;   // SUMO's default
static const int NEXT_ROADS = 12;                       // roads of the route sent with the alert (the stretch ahead_m covers)

AmbulanceLoop11p::~AmbulanceLoop11p()
{
    cancelAndDelete(sendTimer);
    cancelAndDelete(releaseTimer);
}

void AmbulanceLoop11p::initialize(int stage)
{
    DemoBaseApplLayer::initialize(stage);
    if (stage == 0) {
        sendTimer = new cMessage("ambulance DENM");
        releaseTimer = new cMessage("make way: release");
    }
    else if (stage == 1) {
        active = par("active").boolValue();
        isAmbulance = mobility->getExternalId() == par("ambulanceId").stdstringValue();
        equipped = isAmbulance || uniform(0, 1) < par("equippedShare").doubleValue();
        if (!equipped) findHost()->getDisplayString().setTagArg("i", 1, "gray");
        if (isAmbulance) {
            departedAt = simTime();
            traciVehicle->setColor(TraCIColor(255, 0, 0, 255));
            findHost()->getDisplayString().setTagArg("i", 1, "red");
            if (active) scheduleAt(simTime() + par("alertInterval"), sendTimer);
        }
    }
}

void AmbulanceLoop11p::setVehicleVariable(uint8_t variable, int32_t value)
{
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    c->query(TraCIConstants::CMD_SET_VEHICLE_VARIABLE, TraCIBuffer() << variable << mobility->getExternalId() << TraCIConstants::TYPE_INTEGER << value);
}

void AmbulanceLoop11p::setVehicleVariable(uint8_t variable, const std::string& value)
{
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    c->query(TraCIConstants::CMD_SET_VEHICLE_VARIABLE, TraCIBuffer() << variable << mobility->getExternalId() << TraCIConstants::TYPE_STRING << value);
}

int32_t AmbulanceLoop11p::edgeLaneNumber(const std::string& road)
{
    // SUMO's edge.getLaneNumber: CMD_GET_EDGE_VARIABLE with VAR_LANE_INDEX; the reply is parsed as Veins's own getters parse theirs
    TraCIConnection* c = TraCIScenarioManagerAccess().get()->getConnection();
    TraCIBuffer response = c->query(TraCIConstants::CMD_GET_EDGE_VARIABLE, TraCIBuffer() << static_cast<uint8_t>(TraCIConstants::VAR_LANE_INDEX) << road);
    uint8_t cmdLength; response >> cmdLength;
    uint8_t responseId; response >> responseId;
    uint8_t variable; response >> variable;
    std::string id; response >> id;
    uint8_t type; response >> type;
    int32_t value; response >> value;
    return value;
}

void AmbulanceLoop11p::handleSelfMsg(cMessage* msg)
{
    if (msg == sendTimer) {
        Coord p = mobility->getPositionAt(simTime());
        std::string road = mobility->getRoadId();
        TraCIDemo11pMessage* wsm = new TraCIDemo11pMessage("ambulance DENM");
        populateWSM(wsm);
        std::ostringstream data;
        data << "DENM " << p.x << " " << p.y << " " << road << " " << traciVehicle->getLanePosition();
        std::list<std::string> planned = traciVehicle->getPlannedRoadIds();
        bool after = false; int n = 0;
        for (const std::string& r : planned) {
            if (after && n < NEXT_ROADS) { data << " " << r; n++; }
            if (r == road) after = true;
        }
        wsm->setDemoData(data.str().c_str());
        sendDown(wsm);
        alertsSent++;
        traciVehicle->setParameter("veins.tx", static_cast<int>(alertsSent));
        findHost()->getDisplayString().setTagArg("t", 0, ("DENM sent " + std::to_string(alertsSent)).c_str());
        scheduleAt(simTime() + par("alertInterval"), sendTimer);
    }
    else if (msg == releaseTimer) {
        makingWay = false;
        setVehicleVariable(TraCIConstants::VAR_LANECHANGE_MODE, DEFAULT_LANE_CHANGE_MODE);
        setVehicleVariable(TraCIConstants::VAR_LATALIGNMENT, std::string("center"));
        traciVehicle->setColor(TraCIColor(200, 200, 200, 255));
        findHost()->getDisplayString().setTagArg("i", 1, "");
        findHost()->getDisplayString().setTagArg("t", 0, "");
    }
    else {
        DemoBaseApplLayer::handleSelfMsg(msg);
    }
}

void AmbulanceLoop11p::onWSM(BaseFrame1609_4* frame)
{
    if (isAmbulance || !equipped || !active) return;
    TraCIDemo11pMessage* wsm = check_and_cast<TraCIDemo11pMessage*>(frame);
    std::istringstream data(wsm->getDemoData());
    std::string tag; data >> tag;
    if (tag != "DENM") return;
    alertsReceived++;
    double x, y, ambPos; std::string ambRoad;
    data >> x >> y >> ambRoad >> ambPos;
    std::vector<std::string> next; std::string r;
    while (data >> r) next.push_back(r);
    Coord me = mobility->getPositionAt(simTime());
    if (me.distance(Coord(x, y, me.z)) > par("makewayDistance").doubleValue()) return;
    std::string myRoad = mobility->getRoadId();
    bool ahead = false;
    if (myRoad == ambRoad) ahead = traciVehicle->getLanePosition() > ambPos;         // on the ambulance's road: only in front of it
    else for (const std::string& n : next) if (n == myRoad) ahead = true;            // or on one of the next roads of its route
    if (!ahead) return;
    if (!makingWay) {
        makingWay = true;
        madeWay++;
        int32_t lane = traciVehicle->getLaneIndex();
        int32_t lanes = (myRoad.size() && myRoad[0] == ':') ? 1 : edgeLaneNumber(myRoad);
        setVehicleVariable(TraCIConstants::VAR_LANECHANGE_MODE, RESCUE_LANE_CHANGE_MODE);
        setVehicleVariable(TraCIConstants::VAR_LATALIGNMENT, std::string(lane == lanes - 1 && lanes > 1 ? "left" : "right"));
        traciVehicle->setColor(TraCIColor(0, 200, 0, 255));
        findHost()->getDisplayString().setTagArg("i", 1, "green");
        findHost()->getDisplayString().setTagArg("t", 0, "making way");
    }
    cancelEvent(releaseTimer);
    scheduleAt(simTime() + par("makewayHold"), releaseTimer);
}

void AmbulanceLoop11p::finish()
{
    DemoBaseApplLayer::finish();
    recordScalar("alertsSent", alertsSent);
    recordScalar("alertsReceived", alertsReceived);
    recordScalar("madeWay", madeWay);
    if (isAmbulance) recordScalar("ambulanceTimeInNetwork", (simTime() - departedAt).dbl());
}
