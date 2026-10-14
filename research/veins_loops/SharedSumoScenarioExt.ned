// Veins scenario on a SUMO that ANOTHER process started with --num-clients 2 (Phase 2, 2026-10-12): the plain TraCIScenarioManager
// connects to host:port; the launcher (the Python client) owns the SUMO process, so its outputs are written in full before it ends.
// Same submodules as Veins's own Scenario (org.car2x.veins.nodes.Scenario, GPL-2.0-or-later); road-side units sized from the ini.
import org.car2x.veins.base.connectionManager.ConnectionManager;
import org.car2x.veins.base.modules.BaseWorldUtility;
import org.car2x.veins.modules.mobility.traci.TraCIScenarioManager;
import org.car2x.veins.modules.obstacle.ObstacleControl;
import org.car2x.veins.modules.world.annotations.AnnotationManager;
import org.car2x.veins.nodes.Car;
import org.car2x.veins.nodes.RSU;
import org.car2x.veins.nodes.TrafficLight;
import org.car2x.veins.visualizer.roads.RoadsCanvasVisualizer;

network SharedSumoScenarioExt
{
    parameters:
        double playgroundSizeX @unit(m);
        double playgroundSizeY @unit(m);
        double playgroundSizeZ @unit(m);
        int numRsu = default(0);
        double canvasScale = default(1);   // Qtenv pixels per metre: 0.07 shows an 11 km playground in one window
        @display("bgb=dropUnit($playgroundSizeX),dropUnit($playgroundSizeY);bgs=$canvasScale,m");
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
        manager: TraCIScenarioManager { parameters: @display("p=512,128"); }
        roadsCanvasVisualizer: RoadsCanvasVisualizer { @display("p=300,0"); }
        rsu[numRsu]: RSU { @display("i=device/antennatower"); }
        node[0]: Car { }
        tls[0]: TrafficLight { }
    connections allowunconnected:
}
