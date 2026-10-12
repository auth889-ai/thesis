// The RQ3 ambulance alert as a Veins application (our code, GPL-2.0-or-later as Veins): the ambulance broadcasts an 802.11p alert
// every alertInterval; a car that receives it within makewayDistance applies make-way rule v2 (lane-change mode 1605, keep right).
import org.car2x.veins.modules.application.ieee80211p.DemoBaseApplLayer;

simple AmbulanceAlert11p extends DemoBaseApplLayer
{
    parameters:
        @class(AmbulanceAlert11p);
        string ambulanceId = default("ambulance_alert");
        double alertInterval @unit(s) = default(1s);
        double makewayDistance @unit(m) = default(100m);
        double makewayHold @unit(s) = default(30s);
        double equippedShare = default(1);   // share of cars whose app acts on the alert (drawn per car); the ambulance always sends
        bool guiColours = default(false);    // display only (make gui-veins): alerted cars yellow, the ambulance green; off: Veins's orange / blue
        @display("i=block/app2");
}
