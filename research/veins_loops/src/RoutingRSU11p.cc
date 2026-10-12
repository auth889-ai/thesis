//
// RoutingRSU11p (see RoutingRSU11p.h for the licence: GPL-2.0-or-later, derived from Veins's TraCIDemoRSU11p).
// Once a second: the statuses received in that second are appended to the POI parameter "obs" ("vehicle|road|lanePosition|speed|t;"
// per status; the Python client reads and clears it), and if the POI parameter "adv_seq" changed, every advice in "adv"
// ("msgId|vehicle|road road ...;" per advice) is broadcast as one frame "ADVICE <msgId> <vehicle> <road...>", 10 ms apart.
//
#include "RoutingRSU11p.h"

#include <sstream>

#include "PoiParams.h"
#include "veins/modules/application/traci/TraCIDemo11pMessage_m.h"

using namespace veins;
using namespace omnetpp;

Define_Module(RoutingRSU11p);

RoutingRSU11p::~RoutingRSU11p()
{
    cancelAndDelete(tick);
}

void RoutingRSU11p::initialize(int stage)
{
    DemoBaseApplLayer::initialize(stage);
    if (stage == 0) {
        poiId = par("poiId").stdstringValue();
        active = par("active").boolValue();
        tick = new cMessage("rsu tick");
        findHost()->getDisplayString().setTagArg("t", 0, ("RSU " + poiId).c_str());
        if (active) scheduleAt(simTime() + par("firstTick").doubleValue(), tick);
    }
}

void RoutingRSU11p::onWSM(BaseFrame1609_4* frame)
{
    if (!active) return;
    TraCIDemo11pMessage* wsm = check_and_cast<TraCIDemo11pMessage*>(frame);
    std::istringstream data(wsm->getDemoData());
    std::string tag; data >> tag;
    if (tag != "STATUS") return;
    std::string vid, road, pos, speed, t; data >> vid >> road >> pos >> speed >> t;
    statusReceived++;
    pending += vid + "|" + road + "|" + pos + "|" + speed + "|" + t + ";";
    findHost()->getDisplayString().setTagArg("t", 0, ("RSU " + poiId + ": status rx " + std::to_string(statusReceived) + ", advice tx " + std::to_string(adviceSent)).c_str());
    findHost()->getDisplayString().setTagArg("i", 1, "green");
}

void RoutingRSU11p::handleSelfMsg(cMessage* msg)
{
    if (msg != tick) { DemoBaseApplLayer::handleSelfMsg(msg); return; }
    if (!pending.empty()) {
        loops::setPoiParameter(poiId, "obs", loops::getPoiParameter(poiId, "obs") + pending);
        pending.clear();
    }
    std::string seq = loops::getPoiParameter(poiId, "adv_seq");
    if (!seq.empty() && seq != lastSeq) {
        lastSeq = seq;
        std::string adv = loops::getPoiParameter(poiId, "adv");
        std::istringstream all(adv);
        std::string item; int i = 0;
        while (std::getline(all, item, ';')) {
            if (item.empty()) continue;
            std::string msgId, vid, roads;
            size_t a = item.find('|'), b = item.find('|', a + 1);
            if (a == std::string::npos || b == std::string::npos) continue;
            msgId = item.substr(0, a); vid = item.substr(a + 1, b - a - 1); roads = item.substr(b + 1);
            TraCIDemo11pMessage* wsm = new TraCIDemo11pMessage("advice");
            populateWSM(wsm);
            std::string data = "ADVICE " + msgId + " " + vid + " " + roads;
            wsm->setDemoData(data.c_str());
            wsm->addBitLength(data.size() * 8);
            sendDelayedDown(wsm, 0.01 * i++);
            adviceSent++;
        }
        findHost()->getDisplayString().setTagArg("t", 0, ("RSU " + poiId + ": status rx " + std::to_string(statusReceived) + ", advice tx " + std::to_string(adviceSent)).c_str());
    }
    scheduleAt(simTime() + 1, tick);
}

void RoutingRSU11p::finish()
{
    DemoBaseApplLayer::finish();
    recordScalar("statusReceived", statusReceived);
    recordScalar("adviceSent", adviceSent);
}
