{
 "horizon_s": 7200,
 "source": "/Users/jannatulferdouseva/thesis/route/results/scale0.2/arms_h7200.json",
 "reference_arm": "reactive",
 "decision": "NO_SAFE_ROUTING_ACTION",
 "selected_arm": null,
 "selected_mean_total_vehicle_hours_benefit_pct": null,
 "acceptance_rule": {
  "minimum_paired_seeds": 3,
  "required": [
   "total_vehicle_hours improves on every paired seed",
   "arrivals do not decrease on any paired seed",
   "teleports do not increase on any paired seed"
  ],
  "reference": "reactive"
 },
 "deployable_evaluations": [
  {
   "arm": "predictive_persistence",
   "paired_seeds": [
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20
   ],
   "n": 10,
   "accepted": false,
   "reason": "rejected: does not improve all required network-wide metrics on every paired seed",
   "mean_benefit_pct": {
    "total_vehicle_hours": -29.658524006787765,
    "mean_travel_time_all": -16.3043434575332,
    "total_waiting_s": -61.05173498406822,
    "arrived": 14.052848532224498,
    "teleports": -387.35179659102073
   },
   "per_seed": [
    {
     "seed": 11,
     "arrived": {
      "candidate": 4800,
      "reference": 3957,
      "delta": 843,
      "benefit_pct": 21.30401819560273,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 905.3004166666667,
      "reference": 852.2451361867704,
      "delta": 53.05528047989628,
      "benefit_pct": -6.225354446407678,
      "improved": false
     },
     "teleports": {
      "candidate": 68,
      "reference": 27,
      "delta": 41,
      "benefit_pct": -151.85185185185185,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1207.0672222222222,
      "reference": 973.4533333333334,
      "delta": 233.61388888888882,
      "benefit_pct": -23.9984682253786,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1515776.0,
      "reference": 1138499.0,
      "delta": 377277.0,
      "benefit_pct": -33.13810552314934,
      "improved": false
     }
    },
    {
     "seed": 12,
     "arrived": {
      "candidate": 4450,
      "reference": 4012,
      "delta": 438,
      "benefit_pct": 10.917248255234297,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 992.924434876211,
      "reference": 805.3935437930216,
      "delta": 187.53089108318932,
      "benefit_pct": -23.284379733168425,
      "improved": false
     },
     "teleports": {
      "candidate": 100,
      "reference": 13,
      "delta": 87,
      "benefit_pct": -669.2307692307693,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1281.1483333333333,
      "reference": 942.5341666666667,
      "delta": 338.6141666666666,
      "benefit_pct": -35.9259301829023,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1770050.0,
      "reference": 996109.0,
      "delta": 773941.0,
      "benefit_pct": -77.69641675760384,
      "improved": false
     }
    },
    {
     "seed": 13,
     "arrived": {
      "candidate": 4703,
      "reference": 4164,
      "delta": 539,
      "benefit_pct": 12.944284341978866,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 900.8770833333333,
      "reference": 823.7306981044845,
      "delta": 77.14638522884877,
      "benefit_pct": -9.365486245246537,
      "improved": false
     },
     "teleports": {
      "candidate": 82,
      "reference": 20,
      "delta": 62,
      "benefit_pct": -310.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1201.1694444444445,
      "reference": 989.8497222222222,
      "delta": 211.31972222222225,
      "benefit_pct": -21.348667123713227,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1551331.0,
      "reference": 1088453.0,
      "delta": 462878.0,
      "benefit_pct": -42.52622759090195,
      "improved": false
     }
    },
    {
     "seed": 14,
     "arrived": {
      "candidate": 4564,
      "reference": 4078,
      "delta": 486,
      "benefit_pct": 11.917606669936243,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 933.9710416666667,
      "reference": 782.3334113790681,
      "delta": 151.63763028759854,
      "benefit_pct": -19.382737344720763,
      "improved": false
     },
     "teleports": {
      "candidate": 110,
      "reference": 16,
      "delta": 94,
      "benefit_pct": -587.5,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1245.2947222222222,
      "reference": 928.1516666666666,
      "delta": 317.1430555555555,
      "benefit_pct": -34.16931380347919,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1711832.0,
      "reference": 944658.0,
      "delta": 767174.0,
      "benefit_pct": -81.21182480855505,
      "improved": false
     }
    },
    {
     "seed": 15,
     "arrived": {
      "candidate": 4735,
      "reference": 4097,
      "delta": 638,
      "benefit_pct": 15.572370026848914,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 916.0372916666666,
      "reference": 790.6462871866947,
      "delta": 125.39100447997191,
      "benefit_pct": -15.859304788003566,
      "improved": false
     },
     "teleports": {
      "candidate": 77,
      "reference": 16,
      "delta": 61,
      "benefit_pct": -381.25,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1221.3830555555555,
      "reference": 937.5747222222222,
      "delta": 283.8083333333333,
      "benefit_pct": -30.270476219821287,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1605489.0,
      "reference": 967230.0,
      "delta": 638259.0,
      "benefit_pct": -65.98833783071245,
      "improved": false
     }
    },
    {
     "seed": 16,
     "arrived": {
      "candidate": 4493,
      "reference": 3997,
      "delta": 496,
      "benefit_pct": 12.409306980235176,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 990.9052901023891,
      "reference": 850.5334288443171,
      "delta": 140.37186125807204,
      "benefit_pct": -16.50397932610429,
      "improved": false
     },
     "teleports": {
      "candidate": 110,
      "reference": 29,
      "delta": 81,
      "benefit_pct": -279.3103448275862,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1290.378888888889,
      "reference": 989.4538888888889,
      "delta": 300.92500000000007,
      "benefit_pct": -30.41324142329917,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1809571.0,
      "reference": 1166952.0,
      "delta": 642619.0,
      "benefit_pct": -55.06816047275295,
      "improved": false
     }
    },
    {
     "seed": 17,
     "arrived": {
      "candidate": 4800,
      "reference": 4022,
      "delta": 778,
      "benefit_pct": 19.343610144206863,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 932.1108333333333,
      "reference": 819.3915950334289,
      "delta": 112.71923829990442,
      "benefit_pct": -13.756455275246728,
      "improved": false
     },
     "teleports": {
      "candidate": 71,
      "reference": 10,
      "delta": 61,
      "benefit_pct": -610.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1242.8144444444445,
      "reference": 953.2255555555555,
      "delta": 289.58888888888896,
      "benefit_pct": -30.37989143294756,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1647195.0,
      "reference": 1028073.0,
      "delta": 619122.0,
      "benefit_pct": -60.221599049872914,
      "improved": false
     }
    },
    {
     "seed": 18,
     "arrived": {
      "candidate": 4429,
      "reference": 4048,
      "delta": 381,
      "benefit_pct": 9.412055335968379,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 962.6561753852833,
      "reference": 835.5445100354191,
      "delta": 127.11166534986421,
      "benefit_pct": -15.213033395967846,
      "improved": false
     },
     "teleports": {
      "candidate": 62,
      "reference": 32,
      "delta": 30,
      "benefit_pct": -93.75,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1231.9325,
      "reference": 982.9252777777778,
      "delta": 249.00722222222214,
      "benefit_pct": -25.333280957549892,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1587404.0,
      "reference": 1105777.0,
      "delta": 481627.0,
      "benefit_pct": -43.55552701855799,
      "improved": false
     }
    },
    {
     "seed": 19,
     "arrived": {
      "candidate": 4800,
      "reference": 4407,
      "delta": 393,
      "benefit_pct": 8.917631041524848,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 951.488125,
      "reference": 775.2149084568439,
      "delta": 176.27321654315608,
      "benefit_pct": -22.73862571787333,
      "improved": false
     },
     "teleports": {
      "candidate": 112,
      "reference": 16,
      "delta": 96,
      "benefit_pct": -600.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1268.6508333333334,
      "reference": 987.9683333333334,
      "delta": 280.6825,
      "benefit_pct": -28.410070498210974,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1712094.0,
      "reference": 998000.0,
      "delta": 714094.0,
      "benefit_pct": -71.55250501002004,
      "improved": false
     }
    },
    {
     "seed": 20,
     "arrived": {
      "candidate": 4787,
      "reference": 4064,
      "delta": 723,
      "benefit_pct": 17.790354330708663,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 972.5714583333333,
      "reference": 805.6818823529412,
      "delta": 166.88957598039212,
      "benefit_pct": -20.71407830259283,
      "improved": false
     },
     "teleports": {
      "candidate": 93,
      "reference": 32,
      "delta": 61,
      "benefit_pct": -190.625,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1296.7619444444445,
      "reference": 951.1522222222222,
      "delta": 345.6097222222222,
      "benefit_pct": -36.33590020057544,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1830191.0,
      "reference": 1019272.0,
      "delta": 810919.0,
      "benefit_pct": -79.55864577855567,
      "improved": false
     }
    }
   ]
  }
 ],
 "upper_bound_not_deployable": [
  {
   "arm": "predictive_oracle",
   "paired_seeds": [
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20
   ],
   "n": 10,
   "accepted": false,
   "reason": "rejected: does not improve all required network-wide metrics on every paired seed",
   "mean_benefit_pct": {
    "total_vehicle_hours": -31.715997169326926,
    "mean_travel_time_all": -17.528468992681066,
    "total_waiting_s": -68.09977167089795,
    "arrived": 14.69718800828735,
    "teleports": -499.11138127517444
   },
   "per_seed": [
    {
     "seed": 11,
     "arrived": {
      "candidate": 4702,
      "reference": 3957,
      "delta": 745,
      "benefit_pct": 18.82739449077584,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 961.7933333333333,
      "reference": 852.2451361867704,
      "delta": 109.54819714656287,
      "benefit_pct": -12.854071263664597,
      "improved": false
     },
     "teleports": {
      "candidate": 160,
      "reference": 27,
      "delta": 133,
      "benefit_pct": -492.5925925925926,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1282.391111111111,
      "reference": 973.4533333333334,
      "delta": 308.9377777777777,
      "benefit_pct": -31.736269957585126,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1759925.0,
      "reference": 1138499.0,
      "delta": 621426.0,
      "benefit_pct": -54.582920143100694,
      "improved": false
     }
    },
    {
     "seed": 12,
     "arrived": {
      "candidate": 4687,
      "reference": 4012,
      "delta": 675,
      "benefit_pct": 16.824526420737786,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 949.0725,
      "reference": 805.3935437930216,
      "delta": 143.67895620697834,
      "benefit_pct": -17.83959622153396,
      "improved": false
     },
     "teleports": {
      "candidate": 112,
      "reference": 13,
      "delta": 99,
      "benefit_pct": -761.5384615384615,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1265.43,
      "reference": 942.5341666666667,
      "delta": 322.89583333333337,
      "benefit_pct": -34.25826296305793,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1701317.0,
      "reference": 996109.0,
      "delta": 705208.0,
      "benefit_pct": -70.796268279877,
      "improved": false
     }
    },
    {
     "seed": 13,
     "arrived": {
      "candidate": 4800,
      "reference": 4164,
      "delta": 636,
      "benefit_pct": 15.27377521613833,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 938.7820833333334,
      "reference": 823.7306981044845,
      "delta": 115.05138522884886,
      "benefit_pct": -13.967111520014685,
      "improved": false
     },
     "teleports": {
      "candidate": 70,
      "reference": 20,
      "delta": 50,
      "benefit_pct": -250.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1251.7094444444444,
      "reference": 989.8497222222222,
      "delta": 261.8597222222222,
      "benefit_pct": -26.454492671306166,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1646629.0,
      "reference": 1088453.0,
      "delta": 558176.0,
      "benefit_pct": -51.28158955875908,
      "improved": false
     }
    },
    {
     "seed": 14,
     "arrived": {
      "candidate": 4730,
      "reference": 4078,
      "delta": 652,
      "benefit_pct": 15.988229524276607,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 974.1314583333333,
      "reference": 782.3334113790681,
      "delta": 191.79804695426515,
      "benefit_pct": -24.516151830479888,
      "improved": false
     },
     "teleports": {
      "candidate": 128,
      "reference": 16,
      "delta": 112,
      "benefit_pct": -700.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1298.8419444444444,
      "reference": 928.1516666666666,
      "delta": 370.69027777777774,
      "benefit_pct": -39.938545723789154,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1834996.0,
      "reference": 944658.0,
      "delta": 890338.0,
      "benefit_pct": -94.24977081652831,
      "improved": false
     }
    },
    {
     "seed": 15,
     "arrived": {
      "candidate": 4800,
      "reference": 4097,
      "delta": 703,
      "benefit_pct": 17.158896753722235,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 962.1670833333334,
      "reference": 790.6462871866947,
      "delta": 171.52079614663865,
      "benefit_pct": -21.693745854034166,
      "improved": false
     },
     "teleports": {
      "candidate": 100,
      "reference": 16,
      "delta": 84,
      "benefit_pct": -525.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1282.8894444444445,
      "reference": 937.5747222222222,
      "delta": 345.31472222222226,
      "benefit_pct": -36.830634832364474,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1804009.0,
      "reference": 967230.0,
      "delta": 836779.0,
      "benefit_pct": -86.51292867260113,
      "improved": false
     }
    },
    {
     "seed": 16,
     "arrived": {
      "candidate": 4716,
      "reference": 3997,
      "delta": 719,
      "benefit_pct": 17.988491368526393,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 970.2414583333333,
      "reference": 850.5334288443171,
      "delta": 119.70802948901621,
      "benefit_pct": -14.074464968610627,
      "improved": false
     },
     "teleports": {
      "candidate": 97,
      "reference": 29,
      "delta": 68,
      "benefit_pct": -234.48275862068965,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1293.6552777777779,
      "reference": 989.4538888888889,
      "delta": 304.201388888889,
      "benefit_pct": -30.744372456860336,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1813342.0,
      "reference": 1166952.0,
      "delta": 646390.0,
      "benefit_pct": -55.3913100110373,
      "improved": false
     }
    },
    {
     "seed": 17,
     "arrived": {
      "candidate": 4488,
      "reference": 4022,
      "delta": 466,
      "benefit_pct": 11.586275484833417,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 939.4417662116041,
      "reference": 819.3915950334289,
      "delta": 120.05017117817522,
      "benefit_pct": -14.651135294263973,
      "improved": false
     },
     "teleports": {
      "candidate": 119,
      "reference": 10,
      "delta": 109,
      "benefit_pct": -1090.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1223.3619444444444,
      "reference": 953.2255555555555,
      "delta": 270.13638888888886,
      "benefit_pct": -28.339188696157958,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1719705.0,
      "reference": 1028073.0,
      "delta": 691632.0,
      "benefit_pct": -67.27460014998935,
      "improved": false
     }
    },
    {
     "seed": 18,
     "arrived": {
      "candidate": 4474,
      "reference": 4048,
      "delta": 426,
      "benefit_pct": 10.523715415019764,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 932.7685897435897,
      "reference": 835.5445100354191,
      "delta": 97.22407970817062,
      "benefit_pct": -11.636014424180615,
      "improved": false
     },
     "teleports": {
      "candidate": 142,
      "reference": 32,
      "delta": 110,
      "benefit_pct": -343.75,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1212.5991666666666,
      "reference": 982.9252777777778,
      "delta": 229.67388888888888,
      "benefit_pct": -23.366363047264528,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1673849.0,
      "reference": 1105777.0,
      "delta": 568072.0,
      "benefit_pct": -51.37310687417083,
      "improved": false
     }
    },
    {
     "seed": 19,
     "arrived": {
      "candidate": 4746,
      "reference": 4407,
      "delta": 339,
      "benefit_pct": 7.6923076923076925,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 945.0995833333334,
      "reference": 775.2149084568439,
      "delta": 169.8846748764895,
      "benefit_pct": -21.914526284674384,
      "improved": false
     },
     "teleports": {
      "candidate": 87,
      "reference": 16,
      "delta": 71,
      "benefit_pct": -443.75,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1260.1327777777778,
      "reference": 987.9683333333334,
      "delta": 272.1644444444445,
      "benefit_pct": -27.547891492248688,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1672966.0,
      "reference": 998000.0,
      "delta": 674966.0,
      "benefit_pct": -67.63186372745491,
      "improved": false
     }
    },
    {
     "seed": 20,
     "arrived": {
      "candidate": 4678,
      "reference": 4064,
      "delta": 614,
      "benefit_pct": 15.108267716535433,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 984.0427083333333,
      "reference": 805.6818823529412,
      "delta": 178.36082598039206,
      "benefit_pct": -22.137872265353785,
      "improved": false
     },
     "teleports": {
      "candidate": 80,
      "reference": 32,
      "delta": 48,
      "benefit_pct": -150.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 1312.0569444444445,
      "reference": 951.1522222222222,
      "delta": 360.9047222222223,
      "benefit_pct": -37.94394985263488,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1854090.0,
      "reference": 1019272.0,
      "delta": 834818.0,
      "benefit_pct": -81.90335847546092,
      "improved": false
     }
    }
   ]
  }
 ],
 "offline_benchmarks_not_runtime_actions": [
  {
   "arm": "due",
   "paired_seeds": [
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20
   ],
   "n": 10,
   "accepted": false,
   "reason": "rejected: does not improve all required network-wide metrics on every paired seed",
   "mean_benefit_pct": {
    "total_vehicle_hours": 10.844721764642049,
    "mean_travel_time_all": 14.561569942221738,
    "total_waiting_s": 25.714303884801314,
    "arrived": 3.125784737037037,
    "teleports": -153.750300864525
   },
   "per_seed": [
    {
     "seed": 11,
     "arrived": {
      "candidate": 4582,
      "reference": 3957,
      "delta": 625,
      "benefit_pct": 15.794794035885772,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 711.1246060096659,
      "reference": 852.2451361867704,
      "delta": -141.12053017710457,
      "benefit_pct": 16.558678270494447,
      "improved": true
     },
     "teleports": {
      "candidate": 11,
      "reference": 27,
      "delta": -16,
      "benefit_pct": 59.25925925925926,
      "improved": true
     },
     "total_vehicle_hours": {
      "candidate": 940.0672222222222,
      "reference": 973.4533333333334,
      "delta": -33.38611111111118,
      "benefit_pct": 3.429657074241995,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 861442.0,
      "reference": 1138499.0,
      "delta": -277057.0,
      "benefit_pct": 24.335287075350966,
      "improved": true
     }
    },
    {
     "seed": 12,
     "arrived": {
      "candidate": 3919,
      "reference": 4012,
      "delta": -93,
      "benefit_pct": -2.318045862412762,
      "improved": false
     },
     "mean_travel_time_all": {
      "candidate": 596.6864179468422,
      "reference": 805.3935437930216,
      "delta": -208.70712584617945,
      "benefit_pct": 25.91368250399275,
      "improved": true
     },
     "teleports": {
      "candidate": 29,
      "reference": 13,
      "delta": 16,
      "benefit_pct": -123.07692307692308,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 679.7252777777778,
      "reference": 942.5341666666667,
      "delta": -262.8088888888889,
      "benefit_pct": 27.88322144525854,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 460327.0,
      "reference": 996109.0,
      "delta": -535782.0,
      "benefit_pct": 53.78748711235417,
      "improved": true
     }
    },
    {
     "seed": 13,
     "arrived": {
      "candidate": 4480,
      "reference": 4164,
      "delta": 316,
      "benefit_pct": 7.588856868395773,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 690.4920399066016,
      "reference": 823.7306981044845,
      "delta": -133.23865819788296,
      "benefit_pct": 16.17502643818946,
      "improved": true
     },
     "teleports": {
      "candidate": 50,
      "reference": 20,
      "delta": 30,
      "benefit_pct": -150.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 903.5855555555555,
      "reference": 989.8497222222222,
      "delta": -86.26416666666671,
      "benefit_pct": 8.714875069419914,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 777866.0,
      "reference": 1088453.0,
      "delta": -310587.0,
      "benefit_pct": 28.53471854090163,
      "improved": true
     }
    },
    {
     "seed": 14,
     "arrived": {
      "candidate": 4376,
      "reference": 4078,
      "delta": 298,
      "benefit_pct": 7.3075036782736635,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 704.241798826852,
      "reference": 782.3334113790681,
      "delta": -78.09161255221613,
      "benefit_pct": 9.98188386388345,
      "improved": true
     },
     "teleports": {
      "candidate": 23,
      "reference": 16,
      "delta": 7,
      "benefit_pct": -43.75,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 900.4513888888889,
      "reference": 928.1516666666666,
      "delta": -27.70027777777773,
      "benefit_pct": 2.984455964751924,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 872854.0,
      "reference": 944658.0,
      "delta": -71804.0,
      "benefit_pct": 7.601057737297519,
      "improved": true
     }
    },
    {
     "seed": 15,
     "arrived": {
      "candidate": 4161,
      "reference": 4097,
      "delta": 64,
      "benefit_pct": 1.5621186233829631,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 662.5737222976029,
      "reference": 790.6462871866947,
      "delta": -128.07256488909184,
      "benefit_pct": 16.19846535228846,
      "improved": true
     },
     "teleports": {
      "candidate": 23,
      "reference": 16,
      "delta": 7,
      "benefit_pct": -43.75,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 813.8613888888889,
      "reference": 937.5747222222222,
      "delta": -123.71333333333337,
      "benefit_pct": 13.195037195553898,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 680715.0,
      "reference": 967230.0,
      "delta": -286515.0,
      "benefit_pct": 29.62222015446171,
      "improved": true
     }
    },
    {
     "seed": 16,
     "arrived": {
      "candidate": 4221,
      "reference": 3997,
      "delta": 224,
      "benefit_pct": 5.604203152364273,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 676.4727433237696,
      "reference": 850.5334288443171,
      "delta": -174.0606855205475,
      "benefit_pct": 20.464884696778668,
      "improved": true
     },
     "teleports": {
      "candidate": 81,
      "reference": 29,
      "delta": 52,
      "benefit_pct": -179.31034482758622,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 851.4161111111111,
      "reference": 989.4538888888889,
      "delta": -138.0377777777777,
      "benefit_pct": 13.950905578105086,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 804163.0,
      "reference": 1166952.0,
      "delta": -362789.0,
      "benefit_pct": 31.088596617512973,
      "improved": true
     }
    },
    {
     "seed": 17,
     "arrived": {
      "candidate": 3516,
      "reference": 4022,
      "delta": -506,
      "benefit_pct": -12.580805569368474,
      "improved": false
     },
     "mean_travel_time_all": {
      "candidate": 718.5559384941675,
      "reference": 819.3915950334289,
      "delta": -100.83565653926132,
      "benefit_pct": 12.306161931664374,
      "improved": true
     },
     "teleports": {
      "candidate": 31,
      "reference": 10,
      "delta": 21,
      "benefit_pct": -210.0,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 752.8869444444445,
      "reference": 953.2255555555555,
      "delta": -200.33861111111105,
      "benefit_pct": 21.016915665290828,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 435109.0,
      "reference": 1028073.0,
      "delta": -592964.0,
      "benefit_pct": 57.67722720079216,
      "improved": true
     }
    },
    {
     "seed": 18,
     "arrived": {
      "candidate": 4181,
      "reference": 4048,
      "delta": 133,
      "benefit_pct": 3.285573122529644,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 645.6960740072202,
      "reference": 835.5445100354191,
      "delta": -189.84843602819888,
      "benefit_pct": 22.72152276126512,
      "improved": true
     },
     "teleports": {
      "candidate": 46,
      "reference": 32,
      "delta": 14,
      "benefit_pct": -43.75,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 794.9236111111111,
      "reference": 982.9252777777778,
      "delta": -188.00166666666667,
      "benefit_pct": 19.126750620525865,
      "improved": true
     },
     "total_waiting_s": {
      "candidate": 666271.0,
      "reference": 1105777.0,
      "delta": -439506.0,
      "benefit_pct": 39.74635030390395,
      "improved": true
     }
    },
    {
     "seed": 19,
     "arrived": {
      "candidate": 4423,
      "reference": 4407,
      "delta": 16,
      "benefit_pct": 0.36305877013841614,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 758.1303700552957,
      "reference": 775.2149084568439,
      "delta": -17.08453840154823,
      "benefit_pct": 2.2038454388805557,
      "improved": true
     },
     "teleports": {
      "candidate": 95,
      "reference": 16,
      "delta": 79,
      "benefit_pct": -493.75,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 990.2025,
      "reference": 987.9683333333334,
      "delta": 2.2341666666666242,
      "benefit_pct": -0.2261374774157698,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1039944.0,
      "reference": 998000.0,
      "delta": 41944.0,
      "benefit_pct": -4.202805611222445,
      "improved": false
     }
    },
    {
     "seed": 20,
     "arrived": {
      "candidate": 4253,
      "reference": 4064,
      "delta": 189,
      "benefit_pct": 4.650590551181103,
      "improved": true
     },
     "mean_travel_time_all": {
      "candidate": 780.7738389050932,
      "reference": 805.6818823529412,
      "delta": -24.90804344784806,
      "benefit_pct": 3.0915481647800926,
      "improved": true
     },
     "teleports": {
      "candidate": 131,
      "reference": 32,
      "delta": 99,
      "benefit_pct": -309.375,
      "improved": false
     },
     "total_vehicle_hours": {
      "candidate": 966.6413888888889,
      "reference": 951.1522222222222,
      "delta": 15.48916666666662,
      "benefit_pct": -1.6284634893117889,
      "improved": false
     },
     "total_waiting_s": {
      "candidate": 1131872.0,
      "reference": 1019272.0,
      "delta": 112600.0,
      "benefit_pct": -11.047100283339482,
      "improved": false
     }
    }
   ]
  }
 ],
 "honesty_label": "DHAKA_SIMULATED_SENSOR_GRAPH"
}