/*
* Copyright (c) 2012 Broadcom Europe Ltd
*
* Licensed to the Apache Software Foundation (ASF) under one or more
* contributor license agreements.  See the NOTICE file distributed with
* this work for additional information regarding copyright ownership.
* The ASF licenses this file to You under the Apache License, Version 2.0
* (the "License"); you may not use this file except in compliance with
* the License.  You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*
*
* A rotating cube rendered with OpenGL|ES. Three images used as textures on the cube faces.
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include <unistd.h>

#include <bcm_host.h>

#include <GLES/gl.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>

#include "cube_texture_and_coords.h"
#include "zlib.h"

#define PATH "./"
#define ANIM_WIDE 256
#define ANIM_HIGH 256
#define ANIM_SIZE 262144
#define LOGO_WIDE 512
#define LOGO_HIGH 256
#define LOGO_SIZE 524288

#ifndef M_PI
   #define M_PI 3.141592654
#endif


char backbr, backbg, backbb;
float backfr, backfg, backfb;

typedef struct
{
   uint32_t screen_width;
   uint32_t screen_height;
// OpenGL|ES objects
   EGLDisplay display;
   EGLSurface surface;
   EGLContext context;
   GLuint tex[2];
// model rotation vector and direction
   GLfloat rot_angle_x_inc;
   GLfloat rot_angle_y_inc;
   GLfloat rot_angle_z_inc;
// current model rotation angles
   GLfloat rot_angle_x;
   GLfloat rot_angle_y;
   GLfloat rot_angle_z;
// current distance from camera
   GLfloat distance;
   GLfloat distance_inc;
// pointers to texture buffers
   unsigned char **tex_buf;
   unsigned int *tex_len;
   unsigned char tex_tex[ANIM_SIZE];
   int tex_num;
   int tex_max;
   unsigned char tex_log[LOGO_SIZE];
   float tex_ang;
} CUBE_STATE_T;

static void init_ogl(CUBE_STATE_T *state);
static void init_model_proj(CUBE_STATE_T *state);
static void update_model(CUBE_STATE_T *state);
static void redraw_scene(CUBE_STATE_T *state);
static void init_textures(CUBE_STATE_T *state);
static void load_tex_images(int argc, char **argv, CUBE_STATE_T *state);
static void exit_func(void);
static volatile int terminate;
static CUBE_STATE_T _state, *state=&_state;


/***********************************************************
 * Name: init_ogl
 *
 * Arguments:
 *       CUBE_STATE_T *state - holds OGLES model info
 *
 * Description: Sets the display, OpenGL|ES context and screen stuff
 *
 * Returns: void
 *
 ***********************************************************/
static void init_ogl(CUBE_STATE_T *state)
{
   int32_t success = 0;
   EGLBoolean result;
   EGLint num_config;

   static EGL_DISPMANX_WINDOW_T nativewindow;

   DISPMANX_ELEMENT_HANDLE_T dispman_element;
   DISPMANX_DISPLAY_HANDLE_T dispman_display;
   DISPMANX_UPDATE_HANDLE_T dispman_update;
   VC_RECT_T dst_rect;
   VC_RECT_T src_rect;

   static const EGLint attribute_list[] =
   {
      EGL_RED_SIZE, 8,
      EGL_GREEN_SIZE, 8,
      EGL_BLUE_SIZE, 8,
      EGL_ALPHA_SIZE, 8,
      EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
      EGL_NONE
   };

   EGLConfig config;

   // get an EGL display connection
   state->display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
   assert(state->display != EGL_NO_DISPLAY);

   // initialize the EGL display connection
   result = eglInitialize(state->display, NULL, NULL);
   assert(EGL_FALSE != result);

   // get an appropriate EGL frame buffer configuration
   result = eglChooseConfig(state->display, attribute_list, &config, 1, &num_config);
   assert(EGL_FALSE != result);

   // create an EGL rendering context
   state->context = eglCreateContext(state->display, config, EGL_NO_CONTEXT, NULL);
   assert(state->context != EGL_NO_CONTEXT);

   // create an EGL window surface
   success = graphics_get_display_size(0 /* LCD */, &state->screen_width, &state->screen_height);
   assert( success >= 0 );
   printf("w=[%d] x h=[%d]\n",state->screen_width,state->screen_height);

   dst_rect.x = 0;
   dst_rect.y = 0;
   dst_rect.width = state->screen_width;
   dst_rect.height = state->screen_height;

   src_rect.x = 0;
   src_rect.y = 0;
   src_rect.width = state->screen_width << 16;
   src_rect.height = state->screen_height << 16;        

   dispman_display = vc_dispmanx_display_open( 0 /* LCD */ );
   dispman_update = vc_dispmanx_update_start(0);

   dispman_element = vc_dispmanx_element_add( dispman_update, dispman_display,
      0/*layer*/, &dst_rect, 0/*src*/,
      &src_rect, DISPMANX_PROTECTION_NONE, 0 /*alpha*/, 0/*clamp*/, 0/*transform*/);

   nativewindow.element = dispman_element;
   nativewindow.width = state->screen_width;
   nativewindow.height = state->screen_height;
   vc_dispmanx_update_submit_sync(dispman_update);

   state->surface = eglCreateWindowSurface(state->display, config, &nativewindow, NULL);
   assert(state->surface != EGL_NO_SURFACE);

   // connect the context to the surface
   result = eglMakeCurrent(state->display, state->surface, state->surface, state->context);
   assert(EGL_FALSE != result);

   // Set background color and clear buffers
   backbr = 0x20; backbg = 0x20; backbb = 0x20;
   backfr = ((float)backbr / (float)255); backfg = ((float)backbg / (float)255); backfb = ((float)backbb / (float)255);

   glClearColor(backfr, backfg, backfb, 1.0f);
   glClear(GL_COLOR_BUFFER_BIT);
   glClear(GL_DEPTH_BUFFER_BIT);
   glShadeModel(GL_FLAT);
}

/***********************************************************
 * Name: init_model_proj
 *
 * Arguments:
 *       CUBE_STATE_T *state - holds OGLES model info
 *
 * Description: Sets the OpenGL|ES model to default values
 *
 * Returns: void
 *
 ***********************************************************/
static void init_model_proj(CUBE_STATE_T *state)
{
   float nearp = 1.0f;
   float farp = 500.0f;
   float hht;
   float hwd;

   glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_NICEST);

   glViewport(0, 0, (GLsizei)state->screen_width, (GLsizei)state->screen_height);

   glMatrixMode(GL_PROJECTION);
   glLoadIdentity();

   hht = nearp * (float)tan(45.0 / 2.0 / 180.0 * M_PI);
   hwd = hht * (float)state->screen_width / (float)state->screen_height;

   glFrustumf(-hwd, hwd, -hht, hht, nearp, farp);

   glEnableClientState(GL_VERTEX_ARRAY);
   glVertexPointer(3, GL_FLOAT, 0, quadx);
}

/***********************************************************
 * Name: update_model
 *
 * Arguments:
 *       CUBE_STATE_T *state - holds OGLES model info
 *
 * Description: Resets the Model projection and rotation direction
 *
 * Returns: void
 *
 ***********************************************************/
static void update_model(CUBE_STATE_T *state)
{
   // reset model position
   glMatrixMode(GL_MODELVIEW);
   glLoadIdentity();
   glTranslatef(0.0f, 0.0f, -50.0f);

   // reset model rotation
   state->rot_angle_x = 0.0f; state->rot_angle_y = 0.0f; state->rot_angle_z = 0.0f;
   state->rot_angle_x_inc = 0.0f; state->rot_angle_y_inc = 0.0f; state->rot_angle_z_inc = 0.0f;
   state->distance = 50.0f;
}

int infl(unsigned char *outp, unsigned int olen, unsigned char *inpt, unsigned int ilen)
{
    int ret;
    z_stream strm;

    /* allocate inflate state */
    strm.zalloc = Z_NULL;
    strm.zfree = Z_NULL;
    strm.opaque = Z_NULL;
    strm.avail_in = 0;
    strm.next_in = Z_NULL;

    ret = inflateInit2(&strm, 16+MAX_WBITS);

    if (ret != Z_OK)
    {
        return ret;
    }

    /* decompress until deflate stream ends or end of file */
    strm.avail_in = ilen;
    strm.next_in = inpt;

    /* run inflate() on input until output buffer not full */
    strm.avail_out = olen;
    strm.next_out = outp;

    ret = inflate(&strm, Z_NO_FLUSH);

    /* clean up and return */
    (void)inflateEnd(&strm);
    return ret;
}

static void trantran(unsigned char *tempbuff, int buffsize)
{
    int x;

    for (x = 0; (x + 3) < buffsize; x += 4)
    {
        if (tempbuff[x + 3] == 0)
        {
            tempbuff[x + 0] = backbr;
            tempbuff[x + 1] = backbg;
            tempbuff[x + 2] = backbb;
        }

        if (tempbuff[x + 3] != 255)
        {
            tempbuff[x + 3] = 255;
        }
    }
}

/***********************************************************
 * Name: redraw_scene
 *
 * Arguments:
 *       CUBE_STATE_T *state - holds OGLES model info
 *
 * Description:   Draws the model and calls eglSwapBuffers
 *                to render to screen
 *
 * Returns: void
 *
 ***********************************************************/
static void redraw_scene(CUBE_STATE_T *state)
{
   // Start with a clear screen
   glClear(GL_COLOR_BUFFER_BIT);
   glMatrixMode(GL_MODELVIEW);

   glEnable(GL_TEXTURE_2D);
   glTexEnvx(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);

   // Need to rotate textures - do this by rotating each cube face
   glRotatef(180.0f, 1.0f, 0.0f, 0.0f); // front face normal along x axis
   glRotatef(270.0f, 0.0f, 0.0f, 1.0f); // front face normal along z axis

   /* ---@@@### SEPARATOR ###@@@--- */

   // Uncompress and load the next image texture data
   infl(state->tex_tex, ANIM_SIZE, state->tex_buf[state->tex_num], state->tex_len[state->tex_num]);
   trantran(state->tex_tex, ANIM_SIZE);

   // Bind new images
   // Setup first texture
   glBindTexture(GL_TEXTURE_2D, state->tex[0]);
   glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, ANIM_WIDE, ANIM_HIGH, 0, GL_RGBA, GL_UNSIGNED_BYTE, state->tex_tex);
   glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, (GLfloat)GL_LINEAR);
   glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, (GLfloat)GL_LINEAR);

   // Draw first (front) face:
   // Bind texture surface to current vertices
   // Need to rotate textures - do this by rotating each cube face
   // Draw first 4 vertices
   glBindTexture(GL_TEXTURE_2D, state->tex[0]);
   glTranslatef(4.0f, 0.0f, 4.0f);
   glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

   /* ---@@@### SEPARATOR ###@@@--- */

   // Draw first (front) face:
   // Bind texture surface to current vertices
   // Need to rotate textures - do this by rotating each cube face
   // Draw first 4 vertices
   glBindTexture(GL_TEXTURE_2D, state->tex[1]);
   glTranslatef(-8.0f, -2.0f, -4.0f);
   glDrawArrays(GL_TRIANGLE_STRIP, 4, 4);

   /* ---@@@### SEPARATOR ###@@@--- */

   // End the draws
   glDisable(GL_TEXTURE_2D);
   eglSwapBuffers(state->display, state->surface);

   state->tex_num = ((state->tex_num + 1) % state->tex_max);
}

/***********************************************************
 * Name: init_textures
 *
 * Arguments:
 *       CUBE_STATE_T *state - holds OGLES model info
 *
 * Description:   Initialise OGL|ES texture surfaces to use image
 *                buffers
 *
 * Returns: void
 *
 ***********************************************************/
static void init_textures(CUBE_STATE_T *state)
{
   int x, y;
   int quads = (3 * 4), coords = (2 * 4);
   GLfloat quadm[] = {-1, -1, 0, /* row */ 1, -1, 0, /* row */ -1, 1, 0, /* row */ 1, 1, 0};
   GLfloat coordm[] = {0.0f, 0.0f, /* row */ 0.0f, 1.0f, /* row */ 1.0f, 0.0f, /* row */ 1.0f, 1.0f};

   // Initialize the vertices and coordinates arrays

   for (x = 0; x < (quads * 2); x += quads)
   {
       for (y = 0; y < quads; ++y)
       {
           quadx[x + y] = (quadm[y] * 4.0f);
       }

       if (x == (quads * 1))
       {
           quadx[x + 7] = (quadx[x + 7] * 2.0f);
           quadx[x + 10] = (quadx[x + 10] * 2.0f);
       }
   }

   for (x = 0; x < (coords * 2); x += coords)
   {
       for (y = 0; y < coords; ++y)
       {
           coordx[x + y] = coordm[y];
       }
   }

   // load three texture buffers but use them on six OGL|ES texture surfaces
   glGenTextures(2, state->tex);

   // Bind new images
   // Setup first texture
   glBindTexture(GL_TEXTURE_2D, state->tex[1]);
   glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, LOGO_WIDE, LOGO_HIGH, 0, GL_RGBA, GL_UNSIGNED_BYTE, state->tex_log);
   glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, (GLfloat)GL_LINEAR);
   glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, (GLfloat)GL_LINEAR);

   // setup overall texture environment
   glTexCoordPointer(2, GL_FLOAT, 0, coordx);
   glEnableClientState(GL_TEXTURE_COORD_ARRAY);
}

/***********************************************************
 * Name: load_tex_images
 *
 * Arguments:
 *       void
 *
 * Description: Loads three raw images to use as textures on faces
 *
 * Returns: void
 *
 ***********************************************************/
static void load_tex_images(int argc, char **argv, CUBE_STATE_T *state)
{
   int bytes_read;
   char filename[256];
   FILE *fileobjc;

   // initialize the state texture data variables
   state->tex_num = 0;
   state->tex_max = 0;
   state->tex_buf = NULL;
   state->tex_len = NULL;

   // read in the logo file
   bzero(filename, 256 * sizeof(char));
   snprintf(filename, 250, "%s.raw", argv[1]);

   fileobjc = fopen(filename, "rb");
   bytes_read = fread(state->tex_log, 1, LOGO_SIZE, fileobjc);
   fclose(fileobjc);

   assert(bytes_read == LOGO_SIZE); // some problem with file?
   trantran(state->tex_log, bytes_read);

   while (1)
   {
       state->tex_buf = realloc(state->tex_buf, (state->tex_max + 1) * sizeof(unsigned char *));
       state->tex_len = realloc(state->tex_len, (state->tex_max + 1) * sizeof(unsigned int));

       // read in a animation file
       bzero(filename, 256 * sizeof(char));
       snprintf(filename, 250, "%s.%d.raw.gz", argv[2], state->tex_max);

       fileobjc = fopen(filename, "rb");

       if (fileobjc == NULL)
       {
           break;
       }

       fseek(fileobjc, 0, SEEK_END);
       state->tex_len[state->tex_max] = ftell(fileobjc);
       fseek(fileobjc, 0, SEEK_SET);

       printf("loading [%s][%d]\n", filename, state->tex_len[state->tex_max]);
       state->tex_buf[state->tex_max] = malloc(state->tex_len[state->tex_max] * sizeof(unsigned char));
       bytes_read = fread(state->tex_buf[state->tex_max], 1, state->tex_len[state->tex_max], fileobjc);
       fclose(fileobjc);

       assert(bytes_read == state->tex_len[state->tex_max]); // some problem with file?

       state->tex_max += 1;
   }

   assert(state->tex_max != 0); // some problem with array?

   state->tex_ang = 0;
}

//------------------------------------------------------------------------------

static void exit_func(void)
// Function to be passed to atexit().
{
   // clear screen
   glClear(GL_COLOR_BUFFER_BIT);
   eglSwapBuffers(state->display, state->surface);

   // Release OpenGL resources
   eglMakeCurrent(state->display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
   eglDestroySurface(state->display, state->surface);
   eglDestroyContext(state->display, state->context);
   eglTerminate(state->display);

   // release texture buffers
   free(state->tex_buf);

   //printf("\ncube closed\n");
} // exit_func()

//==============================================================================

int main(int argc, char **argv)
{
   // Clear application state
   memset(state, 0, sizeof(*state));

   // Start the broadcom host method
   bcm_host_init();

   // Start OGLES
   init_ogl(state);

   // Load the images and textures
   load_tex_images(argc, argv, state);

   // Setup the model world
   init_model_proj(state);

   // initialise the OGLES texture(s)
   init_textures(state);

   while (!terminate)
   {
      usleep(40*1000);
      update_model(state);
      redraw_scene(state);
   }

   exit_func();
   return 0;
}

