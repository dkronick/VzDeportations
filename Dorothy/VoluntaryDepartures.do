
********************************************************************************
* Add up voluntary departures by week
********************************************************************************

* court cases
use "cases.dta", clear

* Keep Venezuelans and Mexicans (for comparison)
keep if nationality == 238 | nationality == 143 /* 238 = Venezuela, 143 = Mexico */

* indicator for voluntary departures
gen voluntarydepartures = (case_outcome == 20)
gen total = 1 

* weeks
gen week = wofd(final_completion_date)

* sum to week level 
collapse (sum) voluntarydepartures total, by(nationality week)

* additional variables
gen ln_departures = ln(voluntarydepartures)
gen ln_total = ln(total)
gen voluntary_pct = voluntarydepartures / total


********************************************************************************
* Some graphs
********************************************************************************

* Number of voluntary departures
twoway (connected voluntarydepartures week if ///
	dofw(week) >= td(01oct2024) & nationality == 238) ///
       (connected voluntarydepartures week if ///
	dofw(week) >= td(01oct2024) & nationality == 143), ///	
	xline(`=tw(2026w1)', lcolor(red)) ///
	legend(order(1 "Venezuela" 2 "Mexico"))
	
* ln Number of voluntary departures
twoway (connected ln_departures week if ///
	dofw(week) >= td(01oct2024) & nationality == 238) ///
       (connected ln_departures week if ///
	dofw(week) >= td(01oct2024) & nationality == 143), ///	
	xline(`=tw(2026w1)', lcolor(red)) ///
	legend(order(1 "Venezuela" 2 "Mexico"))
	
* As a percent of the total
twoway (connected voluntary_pct week if ///
	dofw(week) >= td(01oct2024) & nationality == 238) ///
       (connected voluntary_pct week if ///
	dofw(week) >= td(01oct2024) & nationality == 143), ///	
	xline(`=tw(2026w1)', lcolor(red)) ///
	legend(order(1 "Venezuela" 2 "Mexico"))
	
	
********************************************************************************
* End of do file
********************************************************************************

	
