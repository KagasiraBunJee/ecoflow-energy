# Ecoflow Custom Integration

This is the pet project of mine. In my region there are scheduled (sometimes unscheduled) cutoffs and i got my **Ecoflow Smart Home Panel**. But i faced with the problem i need to have fast switch from grid to battery and viceversa and it does but there is one issue. **EPS Mode**. Battery draining is too high in this mode and i need to have it on only few  minutes before cutoff. I tried to use automation from the Ecoflow App, but i am a bit lazy to do it or update it everytime schedule is changed. And i was using Home Assistant for other appliances at home, so i decided to automate it using Home Assistant. Unfotunately i haven't found any good solutions for HA, so that's why i decied to create the one for myself. And it works amazing!

### Inspired by [tolwi](https://github.com/tolwi/hassio-ecoflow-cloud "tolwi")

## Features

- Using only public api (REST, MQTT)
- Switch of EPS mode
- Switching batteries charging (Smart Home Panel supports connects 2 batteries)
- Changing breakers load modes (Auto, Manual). In Manual mode you can select source of load of any breaker (Only grid, only battery, or turn off)
- Exported almost all data as sensors (battery percentage, breakers load)
