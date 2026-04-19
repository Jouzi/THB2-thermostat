/*
 * setpoint.c
 *
 * Thermostat setpoint storage and helpers.
 */

#include "setpoint.h"

#include "flash_eep.h"

thermostat_setpoint_t setpoint_cfg;

const thermostat_setpoint_t def_setpoint_cfg = {
	.setpoint_c_x2 = SETPOINT_C_X2_DEFAULT,
	.version = 0,
	.reserved = 0
};

static uint8_t setpoint_clamp(uint8_t value_c_x2) {
	if (value_c_x2 < SETPOINT_C_X2_MIN)
		return SETPOINT_C_X2_MIN;
	if (value_c_x2 > SETPOINT_C_X2_MAX)
		return SETPOINT_C_X2_MAX;
	return value_c_x2;
}

void setpoint_reset_defaults(void) {
	setpoint_cfg = def_setpoint_cfg;
}

void setpoint_save(void) {
	flash_write_cfg(&setpoint_cfg, EEP_ID_SETPOINT, sizeof(setpoint_cfg));
}

void setpoint_load(void) {
	if (flash_read_cfg(&setpoint_cfg, EEP_ID_SETPOINT, sizeof(setpoint_cfg)) != sizeof(setpoint_cfg)) {
		setpoint_reset_defaults();
		return;
	}
	setpoint_cfg.setpoint_c_x2 = setpoint_clamp(setpoint_cfg.setpoint_c_x2);
}

bool setpoint_set_c_x2(uint8_t value_c_x2) {
	uint8_t clamped = setpoint_clamp(value_c_x2);
	if (setpoint_cfg.setpoint_c_x2 == clamped)
		return false;
	setpoint_cfg.setpoint_c_x2 = clamped;
	setpoint_cfg.version++;
	setpoint_save();
	return true;
}

bool setpoint_lcd_show_now(void) {
	if ((cfg.flg & FLG_SHOW_SETPOINT) == 0)
		return false;
	// Alternate every 4 seconds between humidity and setpoint.
	return ((clkt.utc_time_sec >> 2) & 0x1) != 0;
}

int16_t setpoint_lcd_value(void) {
	if (cfg.flg & FLG_SHOW_TF) {
		// F = C*9/5 + 32, where C = setpoint_c_x2 / 2.
		// Rounded to an integer because LCD small number has no decimal point.
		return (int16_t) ((setpoint_cfg.setpoint_c_x2 * 9 + 5) / 10) + 32;
	}
	// Rounded integer Celsius for the same reason.
	return (int16_t) ((setpoint_cfg.setpoint_c_x2 + 1) / 2);
}
