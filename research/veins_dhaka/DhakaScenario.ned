// The Dhaka corridor for Veins: Veins's own Scenario (cars, obstacles, annotations, connection manager), no road-side unit.
import org.car2x.veins.nodes.Scenario;
import org.car2x.veins.nodes.TrafficLight;

network DhakaScenario extends Scenario
{
    submodules:
        tls[0]: TrafficLight {
        }
}
