// RoutingRSU11p (GPL-2.0-or-later, see RoutingRSU11p.h): a road-side unit of the forecast-routing loop in Veins.
import org.car2x.veins.modules.application.ieee80211p.DemoBaseApplLayer;

simple RoutingRSU11p extends DemoBaseApplLayer
{
    parameters:
        @class(RoutingRSU11p);
        string poiId = default("");                      // the SUMO POI (added by the Python client at this unit's position) that carries obs / adv / adv_seq
        bool active = default(true);                     // false: nothing received is recorded, nothing is sent (the baseline arm)
        double firstTick @unit(s) = default(1s);
        @display("i=block/app2");
}
