export default class Config {
  transitRoutingEnabled = false;
  maxBounds: [number, number, number, number] | null = null;
  aboutUrl?: string;
  aboutLinkText?: string;
  contactUrl?: string;
  contactLinkText?: string;
  // TrafficTwin change: the first view when the visitor has none stored (served by backend/app/routing/headway_adapter.py)
  initialCenter?: [number, number] | null;
  initialZoom?: number;

  static shared: Config = new Config();

  public static get transitRoutingEnabled(): boolean {
    return Config.shared.transitRoutingEnabled;
  }

  public static get maxBounds(): [number, number, number, number] | null {
    return Config.shared.maxBounds;
  }

  public static get aboutUrl(): string | undefined {
    return Config.shared.aboutUrl;
  }

  public static get aboutLinkText(): string | undefined {
    return Config.shared.aboutLinkText;
  }

  public static get contactUrl(): string | undefined {
    return Config.shared.contactUrl;
  }

  // TrafficTwin change
  public static get initialCenter(): [number, number] | null | undefined {
    return Config.shared.initialCenter;
  }

  // TrafficTwin change
  public static get initialZoom(): number | undefined {
    return Config.shared.initialZoom;
  }

  public static get contactLinkText(): string | undefined {
    return Config.shared.contactLinkText;
  }
}
