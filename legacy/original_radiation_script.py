import math
n=int(input("Enter the Day of the year:"))
L=float(input("enter longitude of the location:"))
h=input("enter the hemishphere E or W:")
Lstd=float(input("enter standard longitude of the location, for india Use Lstd = 82.5:"))
phi=float(input("enter latitude of the location:"))
IST=float(input("enter the standard time in decimal form, eg: 14.50 for 2:30 pm:"))
b=(n-1)*(360/365)*math.pi/180
e = 229.18*(0.000075 + 0.001868*math.cos(b)-0.032077*math.sin(b)-0.014615*math.cos(2*b)-0.04089*math.sin(2*b))
Lstd = 82.5
if(h=="E"):
 LAT = float(IST-((82.5-L)/15) + (e/60))
elif(h=="W"):
 LAT = float(IST+((82.5-L)/15) + (e/60))
else:
 print("Error")
#print (LAT)
omega=float((LAT-12)*15)
#print ("omega",omega)
delta=float(23.45*math.sin((284+n)*(360/365)*math.pi/180))
#print("delta",delta)
zen=(math.cos(delta*math.pi/180)*math.cos(omega*math.pi/180)*math.cos(phi*math.pi/180))-(math.sin(delta*math.pi/180)*math.sin(phi*math.pi/180))
print("costhethaZ",zen)
thetaZ = math.acos(zen)*180/math.pi
print("Zenith angle",thetaZ)
a = input("Enter Model no: 1.Ig and Id values\n2.Ig, Ibn values: ")

if a == "1":
    Ig = float(input("Enter Ig value: "))
    Id = float(input("Enter Id value: "))
    Ib = Ig-Id

elif a == "2":
     Ig = float(input("Enter Ig value: "))
     Ibn = float(input("Enter Ibn value: "))
     Ib=Ibn*zen
     Id=Ig-Ib
else:
    print("Invalid input.")
beta=float(input("enter the tilt angle:"))
rb=float(1/zen)
rd=float(0.5*(1+math.cos(math.pi/180*beta)))
rho=float(input("enter albedo:"))
rr=0.5*(1-math.cos(math.pi/180*beta))*rho
Model=input("Enter Model No: ,1.Isotropic Model,2.Anisotropic Model")
if(Model=="1"):
 It=(Ib*rb)+(Id*rd)+(Ig*rr)
 print("It Isotropic model:",It)
elif Model== "2":
 Ai=float(input("Enter Anisotropic Index:"))
 Io=1367*(1+0.033*math.cos(360*n/365))*zen
 Itnew=((Ib+Id*Ai)*rb)+(Id*rd*(1-Ai))*(1+math.pow((Ib/Ig),0.5)*math.pow((math.sin(math.pi*beta/360)),3))+Ig*rr
 print("Anisotropic model It:",Itnew)
else:
    print("Invalid model")
