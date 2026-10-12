// The RQ3 ambulance alert in Veins (see AmbulanceAlert11p.ned). Uses Veins's own TraCI connection for the two SUMO commands of
// make-way rule v2 that Veins's command interface does not wrap (lane-change mode, lateral alignment); Veins itself is unchanged.
#pragma once
#include "veins/modules/application/ieee80211p/DemoBaseApplLayer.h"

class AmbulanceAlert11p : public veins::DemoBaseApplLayer {
public:
    void initialize(int stage) override;
    void finish() override;

protected:
    bool isAmbulance = false;
    bool makingWay = false;
    bool equipped = true;
    simtime_t departedAt = -1;
    long alertsSent = 0, alertsReceived = 0, madeWay = 0;
    omnetpp::cMessage* sendTimer = nullptr;
    omnetpp::cMessage* releaseTimer = nullptr;

    void onWSM(veins::BaseFrame1609_4* wsm) override;
    void handleSelfMsg(omnetpp::cMessage* msg) override;
    void handlePositionUpdate(omnetpp::cObject* obj) override;
    void setVehicleVariable(uint8_t variable, int32_t value);
    void setVehicleVariable(uint8_t variable, const std::string& value);
public:
    ~AmbulanceAlert11p() override;
};
