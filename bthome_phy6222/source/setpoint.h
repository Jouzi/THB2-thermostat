/*
 * setpoint.h
 *
 * Thermostat setpoint storage and helpers.
 */

#ifndef _SETPOINT_H_
#define _SETPOINT_H_

#include "config.h"

// Setpoint in 0.5 C steps, range 4.0 .. 28.0 C
#define SETPOINT_C_X2_MIN      8
#define SETPOINT_C_X2_MAX      56
#define SETPOINT_C_X2_DEFAULT  42  // 21.0 C

typedef struct __attribute__((packed)) _thermostat_setpoint_t {
	uint8_t  setpoint_c_x2; // degrees C * 2 (0.5 C steps)
	uint16_t version;       // increments on each committed change
	uint8_t  reserved;
} thermostat_setpoint_t;

extern thermostat_setpoint_t setpoint_cfg;
extern const thermostat_setpoint_t def_setpoint_cfg;

void setpoint_reset_defaults(void);
void setpoint_load(void);
void setpoint_save(void);
bool setpoint_set_c_x2(uint8_t value_c_x2);

// LCD helper functions (integer display only on small number area)
bool setpoint_lcd_show_now(void);
int16_t setpoint_lcd_value(void);

#endif /* _SETPOINT_H_ */
