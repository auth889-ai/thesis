// AmbulanceLoopRSU11p (GPL-2.0-or-later, see AmbulanceLoopRSU11p.h): the junction's road-side unit; a real DENM reception flags its light.
import org.car2x.veins.modules.application.ieee80211p.DemoBaseApplLayer;

simple AmbulanceLoopRSU11p extends DemoBaseApplLayer
{
    parameters:
        @class(AmbulanceLoopRSU11p);
        string tlsId = default("");          // the SUMO traffic light this unit stands at
        bool active = default(true);         // false: receptions are counted but no flag is written (the arms without V2I)
        @display("i=block/app2");
}
