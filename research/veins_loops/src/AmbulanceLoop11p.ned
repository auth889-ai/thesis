// AmbulanceLoop11p (GPL-2.0-or-later, see AmbulanceLoop11p.h): the ambulance's DENM-like 802.11p alert and the cars' make-way rule v2.
import org.car2x.veins.modules.application.ieee80211p.DemoBaseApplLayer;

simple AmbulanceLoop11p extends DemoBaseApplLayer
{
    parameters:
        @class(AmbulanceLoop11p);
        string ambulanceId = default("ambulance_alert");
        double alertInterval @unit(s) = default(1s);
        double makewayDistance @unit(m) = default(100m);
        double makewayHold @unit(s) = default(30s);
        double equippedShare = default(1);   // share of cars whose app acts on the alert (drawn per car); the ambulance always sends
        bool active = default(true);         // false: no frame is sent or acted on (the arms without V2X; the radio stays modelled)
        @display("i=block/app2");
}
