// RoutingCar11p (GPL-2.0-or-later, see RoutingCar11p.h): a connected car of the forecast-routing loop in Veins.
import org.car2x.veins.modules.application.ieee80211p.DemoBaseApplLayer;

simple RoutingCar11p extends DemoBaseApplLayer
{
    parameters:
        @class(RoutingCar11p);
        double statusInterval @unit(s) = default(10s);   // the loop's status_period_s
        string logPoi = default("v2x_log");              // SUMO POI whose "log" parameter carries every route-change outcome to the Python client
        bool active = default(true);                     // false: no frame sent or acted on (the baseline arm; the radio stays modelled)
        bool guiColours = default(false);                // display only: connected cars yellow (rerouted cars are always blue)
        @display("i=block/app2");
}
