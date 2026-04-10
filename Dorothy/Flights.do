
********************************************************************************
* Save ICE arrests so as to identify *interior* removals
********************************************************************************

* arrests (to identify interior arrests)
import delimited "arrests-latest.csv", varnames(1) clear 
keep unique_identifier
duplicates drop /* This isn't QUITE right because a person could be arrested after a border deportation? But that'll be a tiny fraction */
rename unique_identifier anonymizedidentifier
gen inarrestsdata = 1
tempfile arrestees 
save `arrestees' 


********************************************************************************
* All removals
********************************************************************************

* removals: 2025 
import delimited "2026-ICLI-00005_Removals_FY25_20260311_Redacted.csv", ///
	   varnames(7) rowrange(7) clear 
tempfile file2025
save `file2025'	   
	   	   
* removals: 2026
import delimited "2026-ICLI-00005_Removals_FY26_20260311_Redacted.csv", ///
	   varnames(7) rowrange(7) clear 
	   
* add 2025
append using `file2025'
duplicates drop


********************************************************************************
* Merge ICE arrests so as to identify interior removals
********************************************************************************

* identify interior removals
drop if anonymizedidentifier == ""
merge m:1 anonymizedidentifier using `arrestees'
drop if _m == 2 
drop _m 

* counts
gen totalremovals = 1
rename inarrestsdata interiorremovals


********************************************************************************
* Keep Venezuelans and flag destination, sum by day
********************************************************************************

* country of origin
keep if citizenshipcountry == "VENEZUELA"

* destination country
gen destination = "VENEZUELA" if departurecountry == "VENEZUELA"
replace destination = "OTHERS" if departurecountry ~= "VENEZUELA"

* date	   
gen int departed_d = date(substr(departeddate,1,10), "YMD")
format departed_d %td

* collapse to port-of-departure--destination--day level
collapse (sum) totalremovals interiorremovals, by(destination portofdeparture departed_d)

* flight count from HRF
gen month = mofd(departed_d)
gen flightcount = .
replace flightcount = 10 if month == tm(2025m4)
replace flightcount = 10 if month == tm(2025m5)
replace flightcount = 8 if month == tm(2025m6)
replace flightcount = 9 if month == tm(2025m7)
replace flightcount = 8 if month == tm(2025m8)
replace flightcount = 7 if month == tm(2025m9)
replace flightcount = 10 if month == tm(2025m10)
replace flightcount = 8 if month == tm(2025m11)
replace flightcount = 3 if month == tm(2025m12)
replace flightcount = 7 if month == tm(2026m1)
replace flightcount = 12 if month == tm(2026m2)

* reshape
reshape wide totalremovals interiorremovals, i(portofdeparture departed_d) j(destination, string)

* these missings are actually zeros
foreach var of varlist total* interior* {
	replace `var' = 0 if `var' == .
}

* flag charters
gsort + month - totalremovalsVENEZUELA
by month: gen order = _n
gen chartertovz = (order <= flightcount)
replace chartertovz = . if flightcount == .

* collapse to removals by mode by day
gen totalremovalsVENEZUELAcharter = totalremovalsVENEZUELA if chartertovz == 1
gen totalremovalsVZcommercial = totalremovalsVENEZUELA if chartertovz == 0
gen interiorremovalsVENEZUELAcharter = interiorremovalsVENEZUELA if chartertovz == 1
gen interiorremovalsVZcommercial = interiorremovalsVENEZUELA if chartertovz == 0
collapse (sum) total* interior*, by(departed_d)

********************************************************************************
* What's growing?
********************************************************************************

/* collapse to week level
gen week = wofd(departed_d)
collapse (sum) interiorremovals* total*, by(week)

twoway (bar interiorremovalsVENEZUELAcharter week if week >= wofd(td(10apr2024))) ///
(bar  interiorremovalsVZcommercial week if week >= wofd(td(10apr2024))) ///
(bar interiorremovalsOTHERS week if week >= wofd(td(10apr2024))) */
		 
* collapse to pre/post
gen period = "pre" if departed_d >= td(01jul2025) & departed_d <= td(10dec2025)
replace period = "post" if departed_d >= td(16jan2026) & departed_d <= td(10mar2026)		 

* collapse to period		 
collapse (mean) *removals*, by(period)
drop if period == ""		 

* reshape
reshape long totalremovals interiorremovals, i(period) j(mode, string)
reshape wide totalremovals interiorremovals, i(mode) j(period, string)
order mode interiorremovalspre interiorremovalspost totalremovalspre totalremovalspost
		 
* look at the data
replace mode = "OTHER DESTINATIONS" if mode == "OTHERS"
replace mode = "TO VENEZUELA ALL MODES" if mode == "VENEZUELA"
br

********************************************************************************
* End
********************************************************************************
