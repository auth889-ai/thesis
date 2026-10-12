# Draft question for AWS Support — to be sent by the account owner, not sent by anyone yet

Subject: Amazon Location Service Routes API — data provider, periodic polling, storage and derived use (Service Terms 82.4)

Hello,

We are a university research project (undergraduate thesis on road traffic) using the Amazon Location Service Routes API
(`geo-routes` CalculateRoutes and SnapToRoads) in account 915644996102. We want to be sure our use is within the AWS
Service Terms, section 82, and would be grateful for written answers to the following.

1. Provider. Which Geolocation Provider serves `geo-routes` CalculateRoutes and SnapToRoads requests in us-west-2,
   us-east-1 and ap-south-1? Section 82.4(a)(i) allows storing route results "for up to 30 days when you use HERE or
   Esri as your Geolocation Provider"; we need to know whether that exception applies to us.

2. Periodic polling. Section 82.4(a) says we may not "scrape, systematically collect, duplicate, store, or cache"
   Location Data. Is calling CalculateRoutes for a fixed set of about 12 origin–destination pairs every 5 minutes,
   to observe how travel time changes over the day, permitted? If it is permitted only with limits, what are they?

3. Derived values. From each route result we compute one number, average speed = distance ÷ duration, and keep only
   that number with a timestamp. Is such a derived value "Location Data" subject to the 30-day limit?

4. Forecasting and research. May route results, or values derived from them, be used within the 30 days
   (a) as input to a time-series forecasting model at inference time, without training on them, and
   (b) to measure the accuracy of our own forecasts, keeping only the resulting error statistics (for example a
   mean absolute error per day) beyond 30 days?
   May they be used (c) to train or fine-tune a model? Does section 82.4(b) (products "similar to the services of the
   Geolocation Providers") apply to a research prototype that forecasts corridor travel times?

5. SnapToRoads. Our users can opt in to share their own GPS positions; we snap them with SnapToRoads and aggregate
   speeds into 70 m cells in 5-minute bins. The raw and snapped positions are deleted after 24 hours. May the
   aggregated cells (cell id, time bin, count, mean speed), whose location was assigned using snapped positions, be
   kept longer than 30 days?

6. Traffic coverage. For routes in Dhaka, Bangladesh, CalculateRoutes returns the same duration with
   Traffic.Usage=UseTrafficData and IgnoreTrafficData, and TypicalDuration equals BestCaseDuration. Can you confirm
   that no real-time or historical traffic is available for Bangladesh through the Routes API, and whether that is
   expected to change?

For context: we have stopped periodic polling and apply a rolling 30-day deletion to stored values until we hear from you.

Thank you.
