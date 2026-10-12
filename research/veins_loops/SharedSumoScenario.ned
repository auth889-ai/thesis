// Veins scenario whose SUMO is shared with a second TraCI client (2026-10-12, feasibility spike for the Veins loops).
// Same submodules as Veins's own Scenario (org.car2x.veins.nodes.Scenario, GPL-2.0-or-later), with the Forker manager so the
// SUMO command line can carry --num-clients 2; road-side units and traffic lights are sized from the ini.
import org.car2x.veins.base.connectionManager.ConnectionManager;
import org.car2x.veins.base.modules.BaseWorldUtility;
import org.car2x.veins.modules.mobility.traci.TraCIScenarioManagerForker;
import org.car2x.veins.modules.obstacle.ObstacleControl;
import org.car2x.veins.modules.world.annotations.AnnotationManager;
import org.car2x.veins.nodes.Car;
import org.car2x.veins.nodes.RSU;
import org.car2x.veins.nodes.TrafficLight;
import org.car2x.veins.visualizer.roads.RoadsCanvasVisualizer;

network SharedSumoScenario
{
    parameters:
        double playgroundSizeX @unit(m);
        double playgroundSizeY @unit(m);
        double playgroundSizeZ @unit(m);
        int numRsu = default(0);
        @display("bgb=dropUnit($playgroundSizeX),dropUnit($playgroundSizeY)");
    submodules:
        obstacles: ObstacleControl { @display("p=240,50"); }
        annotations: AnnotationManager { @display("p=260,50"); }
        connectionManager: ConnectionManager { parameters: @display("p=150,0;i=abstract/multicast"); }
        world: BaseWorldUtility {
            parameters:
                playgroundSizeX = veins_eval_by_version(veins_omnetpp_buildnum(), "playgroundSizeX", 1525, "parent.playgroundSizeX");
                playgroundSizeY = veins_eval_by_version(veins_omnetpp_buildnum(), "playgroundSizeY", 1525, "parent.playgroundSizeY");
                playgroundSizeZ = veins_eval_by_version(veins_omnetpp_buildnum(), "playgroundSizeZ", 1525, "parent.playgroundSizeZ");
                @display("p=30,0;i=misc/globe");
        }
        manager: TraCIScenarioManagerForker { parameters: @display("p=512,128"); }
        roadsCanvasVisualizer: RoadsCanvasVisualizer { @display("p=300,0"); }
        rsu[numRsu]: RSU { @display("i=device/antennatower"); }
        node[0]: Car { }
        tls[0]: TrafficLight { }
    connections allowunconnected:
}
