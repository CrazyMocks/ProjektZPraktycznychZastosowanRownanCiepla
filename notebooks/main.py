import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as patches
from matplotlib.collections import PatchCollection
import matplotlib.animation as animation
from utils import KtoC, CtoK


Nh = 100
Nt = 48000
tMin = 0
tMax = 36000
xMin = -100
xMax = 100
yMin = -100
yMax = 100
sourceXMin = -30
sourceXMax = 30
sourceYMin = 70
sourceYMax = 90
P = 2000 #W
alpha= 1.25
lambdaWall = 0.2 #W/mk
lambdaWindow = 20.9 #W/mk

# --- Window params ---
u_outside = CtoK(-20.0)       # Temperatura na zewnątrz
c = 1000 #J/kgK
p = 100*1013 #Pa
r = 287 #J/kgK

# --- Grid ---
x = np.linspace(xMin,xMax,Nh)
y = np.linspace(yMin,yMax,Nh)
T = np.linspace(tMin, tMax, Nt)
h=x[1]-x[0]
dt = T[1]-T[0]
X, Y = np.meshgrid(x,y)


uInit = np.zeros_like(X)
uInit[:,:] = CtoK(-20)
u=uInit.copy()
# --- Masks ---

roomMask = ((X >= xMin) & (Y>=yMin) & (X <= xMax) & (Y<=yMax))
heaterMask = roomMask & ((X > sourceXMin) & (Y>sourceYMin) & (X<sourceXMax) & (Y<sourceYMax))
isTop = (Y == yMax)
isBottom = (Y == yMin)
isRight = (X == xMax)
isLeft = (X == xMin)
windowMask = isTop & (X>sourceXMin) & (X<sourceXMax)
wallMask = (isTop | isBottom | isLeft | isRight) & (~windowMask)
roomMask = roomMask & (~windowMask) & (~wallMask)

# stability check
if(dt > 0.34*h**2):
    print(f"Rozwiązanie będzie niestabilne (dt>0.34*h**2): {dt:.5f}>{0.34*h**2:.5f}")
else:
    print("Jest okej!")

def F(u):
    du_dt = np.zeros_like(u)
    u_central = u[1:-1, 1:-1]
    u_left    = u[1:-1, :-2]
    u_right   = u[1:-1, 2:]
    u_up      = u[2:, 1:-1]
    u_down    = u[:-2, 1:-1]
    laplacian = (u_left + u_right + u_up + u_down - 4*u_central) / h**2
    du_dt[1:-1, 1:-1] = alpha*laplacian
    heaterU = np.mean(u[heaterMask])
    du_dt[heaterMask] += (P*r*heaterU)/(c*p*h**2)
    du_dt[wallMask] -= lambdaWall * (u[wallMask] - u_outside)
    du_dt[windowMask] -= lambdaWindow * (u[windowMask] - u_outside)
    return du_dt

def animationGenAndSave(uHistory,filename):
    frameGoal = 100
    sampling = int(len(T)/frameGoal)

    fig, ax = plt.subplots(figsize=(6, 6))

    # vmin = np.min(uHistory)
    vmin = np.min(KtoC(uHistory))
    vmax = np.max(KtoC(uHistory))

    frame0 = KtoC(uHistory[0, :, :].copy())

    im = ax.imshow(frame0, 
                origin='lower', 
                extent=[xMin, xMax, yMin, yMax], 
                vmin=vmin, vmax=vmax, 
                cmap='coolwarm')

    plt.colorbar(im, label='Temperatura u(x,y)')
    title = ax.set_title(f"Czas t = {T[0]:.2f}")
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    def update(frame_idx):
        current_u = KtoC(uHistory[frame_idx, :, : ].copy())
        im.set_data(current_u)
        current_time = T[frame_idx*sampling]
        title.set_text(f"Czas t = {current_time:.2f}")
        return im, title

    ani = animation.FuncAnimation(fig, update, frames=int(len(T)/sampling), interval=50, blit=False)
    ani.save(filename, fps=20)

# fig, ax = plt.subplots()
# rects = []
# size = 1
# for x, y in zip(X[roomMask & ~heaterMask & ~wallMask & ~windowMask], Y[roomMask & ~heaterMask & ~wallMask & ~windowMask]):
#     rects.append(patches.Rectangle((x-h/2, y-h/2), width=h*size, height=h*size))
# pc = PatchCollection(rects,facecolor='gray')
# ax.add_collection(pc)
# rects = []
# for x, y in zip(X[heaterMask], Y[heaterMask]):
#     rects.append(patches.Rectangle((x-h/2, y-h/2), width=h*size, height=h*size))
# pc = PatchCollection(rects,facecolor='red')
# ax.add_collection(pc)
# rects = []
# for x, y in zip(X[wallMask], Y[wallMask]):
#     rects.append(patches.Rectangle((x-h/2, y-h/2), width=h*size, height=h*size))
# pc = PatchCollection(rects,facecolor='black')
# ax.add_collection(pc)
# rects = []
# for x, y in zip(X[windowMask], Y[windowMask]):
#     rects.append(patches.Rectangle((x-h/2, y-h/2), width=h*size, height=h*size))
# pc = PatchCollection(rects,facecolor='blue')
# ax.add_collection(pc)

# plt.xlim((xMin-h/2,xMax+h/2))
# plt.ylim((yMin-h/2,yMax+h/2))
# plt.axis('off')
# ax.set_aspect('equal')
# plt.title('Obszar L')
# legend_elements = [
#     patches.Patch(facecolor='gray', label='Pokój - Scenariusz A'),
#     patches.Patch(facecolor='red', label='Grzejnik'),
#     patches.Patch(facecolor='black', label='Ściana'),
#     patches.Patch(facecolor='blue', label='Okno')
# ]
# ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.95, 1.05))
# plt.show()


temperatureHistoryA = []
sigmaA = []
numOfFrames = 100
interval = int(len(T)/numOfFrames)
uHistoryA = np.zeros((numOfFrames, uInit.shape[0],uInit.shape[1]))
frame=0
u_prev = uInit
for i in range(len(T)):
    temperatureHistoryA.append(np.mean(u_prev))
    sigmaA.append(np.std(u_prev))
    u_next = u_prev + dt * F(u_prev)
    u_prev=u_next
    if (i%interval==0):
        uHistoryA[frame] = u_next
        frame+=1
animationGenAndSave(uHistoryA, "AnimacjaA.mp4")
print("Animacja zapisana.")
plt.close()
sourceXMin = -30
sourceXMax = 30
sourceYMin = -90
sourceYMax = -70
heaterMask = roomMask & ((X > sourceXMin) & (Y>sourceYMin) & (X<sourceXMax) & (Y<sourceYMax))
temperatureHistoryB = []
sigmaB = []
numOfFrames = 100
interval = int(len(T)/numOfFrames)
uHistoryB = np.zeros((numOfFrames, uInit.shape[0],uInit.shape[1]))
frame=0
u_prev = uInit
for i in range(len(T)):
    temperatureHistoryB.append(np.mean(u_prev))
    sigmaB.append(np.std(u_prev))
    u_next = u_prev + dt * F(u_prev)
    u_prev=u_next
    if (i%interval==0):
        uHistoryB[frame] = u_next
        frame+=1
animationGenAndSave(uHistoryB, "AnimacjaB.mp4")
print("Animacja zapisana.")
plt.close()

plt.plot(T, KtoC(np.array(temperatureHistoryA)))
plt.plot(T, KtoC(np.array(temperatureHistoryB)))
plt.xlabel("Czas t")
plt.ylabel("Średnia temperatura [°C]")
plt.title("Średnia temperatura w funkcji czasu")
plt.show()

plt.plot(T, sigmaA)
plt.plot(T, sigmaB)
plt.xlabel("Czas t")
plt.ylabel("Odchylenie standardowe temperatury")
plt.title("Odchylenie standardowe temperatury w funkcji czasu")
plt.show()
