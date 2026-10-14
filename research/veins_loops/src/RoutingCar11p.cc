//
// RoutingCar11p (see RoutingCar11p.h for the licence: GPL-2.0-or-later, derived from Veins's TraCIDemo11p).
// Frames: "STATUS <vehicle> <road> <lanePosition> <speed> <t>" every statusInterval (first at a random offset, as the loop's
// per-vehicle stagger); "ADVICE <msgId> <vehicle> <road...>" from a road-side unit: applied as core/simulation/twin/route_application.py
// does (only when the car still exists and is on an edge of the advised route; on a junction the change waits a second, up to 5 times;
// past the fork it is inapplicable). Every outcome is appended to the SUMO point of interest "v2x_log" (parameter "log"), which the
// Python client reads each second. A car whose route changed turns blue.
//
#include "RoutingCar11p.h"

#include <sstream>

#include "PoiParams.h"
#include "veins/modules/application/traci/TraCIDemo11pMessage_m.h"

using namespace veins;
using namespace omnetpp;

Define_Module(RoutingCar11p);

RoutingCar11p::~RoutingCar11p()
{
    cancelAndDelete(statusTimer);
    cancelAndDelete(deferTimer);
}

void RoutingCar11p::initialize(int stage)
{
    DemoBaseApplLayer::initialize(stage);
    if (stage == 0) {
        statusTimer = new cMessage("status");
        deferTimer = new cMessage("advice: retry off the junction");
    }
    else if (stage == 1) {
        active = par("active").boolValue();
        traciVehicle->setParameter("v2x.connected", 1);                     // the Python client treats exactly the cars that have a radio as connected
        if (par("guiColours").boolValue()) traciVehicle->setColor(TraCIColor(255, 220, 0, 255));
        if (active) scheduleAt(simTime() + uniform(0, par("statusInterval").doubleValue()), statusTimer);
    }
}

void RoutingCar11p::handleSelfMsg(cMessage* msg)
{
    if (msg == statusTimer) {
        std::string road = mobility->getRoadId();
        if (!road.empty() && road[0] != ':') {
            TraCIDemo11pMessage* wsm = new TraCIDemo11pMessage("status");
            populateWSM(wsm);
            std::ostringstream data;
            data << "STATUS " << mobility->getExternalId() << " " << road << " " << traciVehicle->getLanePosition() << " " << mobility->getSpeed() << " " << simTime().dbl();
            wsm->setDemoData(data.str().c_str());
            wsm->addBitLength(data.str().size() * 8);
            sendDown(wsm);
            statusSent++;
            traciVehicle->setParameter("v2x.sent", std::to_string(statusSent) + " " + std::to_string(simTime().dbl()));   // for --explain: count and exact send time of this car's last status
        }
        scheduleAt(simTime() + par("statusInterval"), statusTimer);
    }
    else if (msg == deferTimer) {
        applyAdvice();
    }
    else {
        DemoBaseApplLayer::handleSelfMsg(msg);
    }
}

void RoutingCar11p::logEntry(const std::string& outcome, const std::string& msgId, const std::string& road)
{
    std::ostringstream e;
    e << outcome << "|" << msgId << "|" << mobility->getExternalId() << "|" << simTime().dbl() << "|" << road << "\n";
    loops::setPoiParameter(par("logPoi").stdstringValue(), "log", loops::getPoiParameter(par("logPoi").stdstringValue(), "log") + e.str());
}

void RoutingCar11p::applyAdvice()
{
    std::string road = mobility->getRoadId();
    if (!road.empty() && road[0] == ':') {                                      // SUMO refuses route changes inside a junction: next second
        if (++deferTries <= 5) { adviceDeferred++; scheduleAt(simTime() + 1, deferTimer); return; }
        adviceInapplicable++; logEntry("INAPPLICABLE_ON_JUNCTION", pendingMsgId, road); return;
    }
    std::list<std::string> tail;
    bool found = false;
    for (const std::string& r : pendingRoute) {
        if (r == road) found = true;
        if (found) tail.push_back(r);
    }
    if (!found) { adviceInapplicable++; logEntry("INAPPLICABLE_PAST_FORK", pendingMsgId, road); return; }
    if (traciVehicle->changeVehicleRoute(tail)) {
        adviceApplied++;
        logEntry("APPLIED", pendingMsgId, road);
        traciVehicle->setColor(TraCIColor(30, 100, 255, 255));
        findHost()->getDisplayString().setTagArg("i", 1, "blue");
        findHost()->getDisplayString().setTagArg("t", 0, "rerouted");
    }
    else {
        adviceInapplicable++; logEntry("TRACI_REFUSED", pendingMsgId, road);
    }
}

void RoutingCar11p::onWSM(BaseFrame1609_4* frame)
{
    if (!active) return;
    TraCIDemo11pMessage* wsm = check_and_cast<TraCIDemo11pMessage*>(frame);
    std::istringstream data(wsm->getDemoData());
    std::string tag; data >> tag;
    if (tag != "ADVICE") return;
    std::string msgId, vid; data >> msgId >> vid;
    if (vid != mobility->getExternalId()) return;
    adviceReceived++;
    pendingMsgId = msgId; pendingRoute.clear(); deferTries = 0;
    std::string r;
    while (data >> r) pendingRoute.push_back(r);
    cancelEvent(deferTimer);
    applyAdvice();
}

void RoutingCar11p::finish()
{
    DemoBaseApplLayer::finish();
    recordScalar("statusSent", statusSent);
    recordScalar("adviceReceived", adviceReceived);
    recordScalar("adviceApplied", adviceApplied);
    recordScalar("adviceInapplicable", adviceInapplicable);
    recordScalar("adviceDeferred", adviceDeferred);
}
