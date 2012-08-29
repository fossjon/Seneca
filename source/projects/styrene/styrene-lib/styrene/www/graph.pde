class rectButton
{
    boolean drag;
    int x, y, w, h;
    
    color bordcolor, basecolor, highcolor, clickcolor;
    color prescolor;
    
    String textstri;
    PFont myfont;
    
    rectButton(int ix, int iy, int iw, int ih, color cborder, color cbase, color chigh, color cclick, String tstr)
    {
        drag = false;
        x = ix; y = iy; w = iw; h = ih;
        
        bordcolor = cborder;
        basecolor = cbase;
        highcolor = chigh;
        clickcolor = cclick;
        
        textstri = tstr;
        myfont = createFont("Arial", 14);
        
        prescolor = basecolor;
    }
    
    void display()
    {
        stroke(bordcolor);
        fill(prescolor);
        rect(x, y, w, h);
        
        textFont(myfont);
        fill(bordcolor);
        text(textstri, x + (w / 2) - 4, y + (h / 2) + 4);
    }
    
    int overRect()
    {
        if (mouseX >= x && mouseX <= x+w && mouseY >= y && mouseY <= y+h)
        {
            if (mousePressed)
            {
                drag = true;
                prescolor = clickcolor;
                return 2;
            }
            
            else
            {
                drag = false;
                prescolor = highcolor;
                return 1;
            }
        }
        
        else
        {
            if (mousePressed && drag)
            {
                drag = true;
                prescolor = clickcolor;
                return 2;
            }
            
            else
            {
                drag = false;
                prescolor = basecolor;
                return 0;
            }
        }
    }
    
    void setPos(int ix, int iy)
    {
        x = ix; y = iy;
    }
    
    color getBase()
    {
        return basecolor;
    }
}

class textBox
{
    int h, n, p, l;
    int x, y;
    int q, r;
    int boxxb, boxyb, boxxe, boxye;
    int scrxb, scryb, scrxe, scrye, scriw, scrih;
    int txtxb, txtyb;
    String tmpstr;
    String[] textlist;
    
    color bordcolor, textcolor, basecolor;
    PFont myfont;
    rectButton scroll;
    
    textBox(int ix, int iy, String[] ltext, color cborder, color ctext, color cbase)
    {
        h = 17; n = 10; p = 0; l = ltext.length;
        x = ix; y = iy;
        boxxb = x; boxyb = y; boxxe = (width - x - 5); boxye = (h * n);
        scriw = 10; scrih = 20;
        scrxb = (boxxe - 10); scryb = (y + 5); scrxe = scrxb; scrye = (y + boxye - scrih - 5);
        txtxb = (x + 5); txtyb = (y + 17);
        textlist = ltext;
        
        bordcolor = cborder;
        textcolor = ctext;
        basecolor = cbase;
        myfont = createFont("Arial", 14);
        scroll = new rectButton(scrxb, scryb, scriw, scrih, bordcolor, bordcolor, bordcolor, bordcolor, "");
    }
    
    void display()
    {
        stroke(bordcolor);
        fill(basecolor);
        rect(x, y, boxxe, boxye);
        
        tmpstr = "";
        
        for (int i = p; (i < (p + n)) && (i < l); ++i)
        {
            tmpstr = (tmpstr + textlist[i] + "\n");
        }
        
        textFont(myfont);
        fill(textcolor);
        text(tmpstr, txtxb, txtyb);
        
        scroll.display();
    }
    
    int overBar()
    {
        if (scroll.overRect() == 2)
        {
            q = (scrih / 2); r = (mouseY - q);
            
            if (r < scryb)
            {
                r = scryb;
            }
            
            if (r > scrye)
            {
                r = scrye;
            }
            
            scroll.setPos(scrxb, r);
            p = (int)(((r - scryb) * l) / (scrye - scryb));
            
            if ((l - p) < n)
            {
                p = 0;
                
                if (l > n)
                {
                    p = (l - n);
                }
            }
        }
        
        return 0;
    }
}

String[] builtlist = { %s };
String[] worklist = { %s };
String[] waitlist = { %s };
String[] errolist = { %s };

int init = 0;
String[] templist = null;
color tempcolor;
rectButton builtbar, workbar, waitbar, errobar;
textBox listtext;

void clear()
{
    background(#ffffff);
}

void draw()
{
    if ((builtbar.overRect() == 2) || (init == 0))
    {
        templist = builtlist;
        tempcolor = builtbar.getBase();
    }
    
    builtbar.display();
    
    if (workbar.overRect() == 2)
    {
        templist = worklist;
        tempcolor = workbar.getBase();
    }
    
    workbar.display();
    
    if (waitbar.overRect() == 2)
    {
        templist = waitlist;
        tempcolor = waitbar.getBase();
    }
    
    waitbar.display();
    
    if (errobar.overRect() == 2)
    {
        templist = errolist;
        tempcolor = errobar.getBase();
    }
    
    errobar.display();
    
    if (templist != null)
    {
        listtext = new textBox(5, 40, templist, color(#000000), tempcolor, color(#ffffff));
        init = 1;
        templist = null;
    }
    
    listtext.overBar();
    listtext.display();
}

void setup()
{
    size(800, 220);
    smooth();
    frameRate(30);
    clear();
    
    int w = 0, h = 25, o = 0, p = 30, s = (width - 100 - (4 * p));
    int builtnum = builtlist.length, worknum = worklist.length, waitnum = waitlist.length, erronum = errolist.length;
    int totalnum = (builtnum + worknum + waitnum + erronum);
    
    o += (w + 5);
    w = (((builtnum * s) / totalnum) + p);
    builtbar = new rectButton(o, 5, w, h, color(#000000), color(#0066bb), color(#1076ed), color(#0066bb), builtnum);
    
    o += (w + 0);
    w = (((worknum * s) / totalnum) + p);
    workbar = new rectButton(o, 5, w, h, color(#000000), color(#00d000), color(#10f010), color(#00e000), worknum);
    
    o += (w + 0);
    w = (((waitnum * s) / totalnum) + p);
    waitbar = new rectButton(o, 5, w, h, color(#000000), color(#ffbf00), color(#ffcf10), color(#ffbf00), waitnum);
    
    o += (w + 0);
    w = (((erronum * s) / totalnum) + p);
    errobar = new rectButton(o, 5, w, h, color(#000000), color(#eb0000), color(#fb1010), color(#eb0000), erronum);
}
